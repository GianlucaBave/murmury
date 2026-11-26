// audiotap (Windows): streams live audio to stdout as raw float32, mono, 16 kHz (little endian).
//
//   audiotap system   the PC's audio output (the other people on the call), via WASAPI loopback
//   audiotap mic      the default microphone, via WASAPI capture
//
// Same contract as audiotap/main.swift on macOS: nothing is saved, samples go to stdout only,
// status lines go to stderr, and the helper exits quietly when the reader goes away.
//
// Build (MSVC, "x64 Native Tools Command Prompt"):
//   cl /O2 /EHsc /std:c++17 audiotap\windows\main.cpp /Fe:audiotap\audiotap.exe ole32.lib winmm.lib
// Build (MinGW-w64):
//   g++ -O2 -std=c++17 audiotap/windows/main.cpp -o audiotap/audiotap.exe -lole32 -lwinmm -static

#define WIN32_LEAN_AND_MEAN
#define NOMINMAX
#include <windows.h>
#include <audioclient.h>
#include <mmdeviceapi.h>
#include <timeapi.h>

#include <cstdarg>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <string>
#include <vector>

#ifdef _MSC_VER
#pragma comment(lib, "ole32.lib")
#pragma comment(lib, "winmm.lib")
#endif

static const int kOutRate = 16000;

// Sample sub-formats, spelled out so the build needs neither ksmedia.h nor INITGUID.
static const GUID kSubtypePcm = {0x00000001, 0x0000, 0x0010, {0x80, 0x00, 0x00, 0xAA, 0x00, 0x38, 0x9B, 0x71}};
static const GUID kSubtypeFloat = {0x00000003, 0x0000, 0x0010, {0x80, 0x00, 0x00, 0xAA, 0x00, 0x38, 0x9B, 0x71}};

static void logmsg(const char* format, ...) {
    char line[512];
    va_list args;
    va_start(args, format);
    vsnprintf(line, sizeof(line), format, args);
    va_end(args);
    fprintf(stderr, "audiotap: %s\n", line);
    fflush(stderr);
}

// WriteFile on the raw handle, not fwrite: no text-mode translation can touch the bytes (a 0x0A
// in a float would become 0x0D 0x0A), and a closed pipe is an error we can act on, not a crash.
static void emit(const float* samples, size_t count) {
    if (count == 0) return;
    HANDLE out = GetStdHandle(STD_OUTPUT_HANDLE);
    const char* bytes = reinterpret_cast<const char*>(samples);
    size_t left = count * sizeof(float);
    while (left > 0) {
        DWORD written = 0;
        if (!WriteFile(out, bytes, static_cast<DWORD>(left), &written, nullptr) || written == 0) {
            ExitProcess(0);  // the reader (listen.py) went away
        }
        bytes += written;
        left -= written;
    }
}

// Small RAII holder so every COM pointer is released on every path out of capture().
template <class T>
struct Com {
    T* p = nullptr;
    Com() = default;
    Com(const Com&) = delete;
    Com& operator=(const Com&) = delete;
    ~Com() { if (p) p->Release(); }
    T** operator&() { return &p; }
    T* operator->() const { return p; }
    operator T*() const { return p; }
};

// MARK: sample format

struct Format {
    int channels = 0;
    int rate = 0;
    int bits = 0;
    int blockAlign = 0;
    bool isFloat = false;
};

static bool parseFormat(const WAVEFORMATEX* wf, Format& f) {
    f.channels = wf->nChannels;
    f.rate = static_cast<int>(wf->nSamplesPerSec);
    f.bits = wf->wBitsPerSample;
    f.blockAlign = wf->nBlockAlign;
    if (wf->wFormatTag == WAVE_FORMAT_IEEE_FLOAT) {
        f.isFloat = true;
    } else if (wf->wFormatTag == WAVE_FORMAT_PCM) {
        f.isFloat = false;
    } else if (wf->wFormatTag == WAVE_FORMAT_EXTENSIBLE) {
        const auto* ext = reinterpret_cast<const WAVEFORMATEXTENSIBLE*>(wf);
        if (IsEqualGUID(ext->SubFormat, kSubtypeFloat)) f.isFloat = true;
        else if (IsEqualGUID(ext->SubFormat, kSubtypePcm)) f.isFloat = false;
        else return false;
    } else {
        return false;
    }
    if (f.isFloat) return f.bits == 32;
    return f.bits == 16 || f.bits == 24 || f.bits == 32;
}

static float readSample(const uint8_t* p, const Format& f) {
    if (f.isFloat) {
        float v;
        memcpy(&v, p, 4);
        return v;
    }
    if (f.bits == 16) {
        int16_t v;
        memcpy(&v, p, 2);
        return static_cast<float>(v) / 32768.0f;
    }
    if (f.bits == 24) {
        int32_t v = static_cast<int32_t>((uint32_t)p[0] << 8 | (uint32_t)p[1] << 16 | (uint32_t)p[2] << 24);
        return static_cast<float>(v) / 2147483648.0f;
    }
    int32_t v;
    memcpy(&v, p, 4);
    return static_cast<float>(v) / 2147483648.0f;
}

// MARK: resampler

// Streaming area-average resampler (mono). Each output sample is the mean of the input span it
// covers, which also acts as a cheap low-pass filter: for the usual 48 kHz -> 16 kHz it is an
// exact 3-sample average. Good enough for speech recognition; not meant for music.
class Resampler {
public:
    explicit Resampler(int inRate) : step_(static_cast<double>(inRate) / kOutRate) {}

    void push(float x, std::vector<float>& out) {
        double weight = 1.0;  // how much of this input sample is still unused
        while (weight > 1e-9) {
            double need = step_ - filled_;
            if (weight < need) {
                acc_ += x * weight;
                filled_ += weight;
                weight = 0;
            } else {
                acc_ += x * need;
                out.push_back(static_cast<float>(acc_ / step_));
                weight -= need;
                acc_ = 0;
                filled_ = 0;
            }
        }
    }

private:
    double step_;
    double acc_ = 0;
    double filled_ = 0;
};

// MARK: capture

enum class Result { Reattach, Fatal };

static Result capture(IMMDeviceEnumerator* enumerator, EDataFlow flow) {
    const char* what = (flow == eRender) ? "system audio" : "microphone";

    Com<IMMDevice> device;
    HRESULT hr = enumerator->GetDefaultAudioEndpoint(flow, eConsole, &device);
    if (FAILED(hr)) {
        logmsg("no default %s device yet (0x%08lx); retrying in 1 s", what, static_cast<unsigned long>(hr));
        return Result::Reattach;
    }
    LPWSTR rawId = nullptr;
    device->GetId(&rawId);
    std::wstring deviceId = rawId ? rawId : L"";
    CoTaskMemFree(rawId);

    Com<IAudioClient> client;
    hr = device->Activate(__uuidof(IAudioClient), CLSCTX_ALL, nullptr, reinterpret_cast<void**>(&client));
    if (FAILED(hr)) {
        logmsg("cannot open %s device (0x%08lx); retrying in 1 s", what, static_cast<unsigned long>(hr));
        return Result::Reattach;
    }

    WAVEFORMATEX* mix = nullptr;
    hr = client->GetMixFormat(&mix);
    if (FAILED(hr) || !mix) {
        logmsg("cannot read the device format (0x%08lx); retrying in 1 s", static_cast<unsigned long>(hr));
        return Result::Reattach;
    }
    Format fmt;
    if (!parseFormat(mix, fmt)) {
        logmsg("unsupported device format (tag 0x%04x, %d bits)", mix->wFormatTag, mix->wBitsPerSample);
        CoTaskMemFree(mix);
        return Result::Fatal;
    }

    // Loopback taps the render endpoint's mix; for the microphone it is a plain capture stream.
    DWORD flags = (flow == eRender) ? AUDCLNT_STREAMFLAGS_LOOPBACK : 0;
    const REFERENCE_TIME bufferDuration = 10'000'000;  // 1 s, in 100 ns units
    hr = client->Initialize(AUDCLNT_SHAREMODE_SHARED, flags, bufferDuration, 0, mix, nullptr);
    CoTaskMemFree(mix);
    if (FAILED(hr)) {
        logmsg("cannot start %s capture (0x%08lx); retrying in 1 s", what, static_cast<unsigned long>(hr));
        return Result::Reattach;
    }

    Com<IAudioCaptureClient> reader;
    hr = client->GetService(__uuidof(IAudioCaptureClient), reinterpret_cast<void**>(&reader));
    if (FAILED(hr)) {
        logmsg("cannot get the capture service (0x%08lx)", static_cast<unsigned long>(hr));
        return Result::Reattach;
    }
    hr = client->Start();
    if (FAILED(hr)) {
        logmsg("cannot start the stream (0x%08lx); retrying in 1 s", static_cast<unsigned long>(hr));
        return Result::Reattach;
    }
    logmsg("%s started (%d Hz mono, from %d Hz x %d ch)", what, kOutRate, fmt.rate, fmt.channels);

    LARGE_INTEGER freq, start;
    QueryPerformanceFrequency(&freq);
    QueryPerformanceCounter(&start);
    uint64_t emitted = 0;  // output samples written in this session
    ULONGLONG lastDeviceCheck = GetTickCount64();
    Resampler resampler(fmt.rate);
    std::vector<float> out;
    out.reserve(4096);
    std::vector<float> zeros;

    for (;;) {
        bool gotData = false;
        UINT32 packet = 0;
        hr = reader->GetNextPacketSize(&packet);
        while (SUCCEEDED(hr) && packet > 0) {
            BYTE* data = nullptr;
            UINT32 frames = 0;
            DWORD bufferFlags = 0;
            hr = reader->GetBuffer(&data, &frames, &bufferFlags, nullptr, nullptr);
            if (FAILED(hr)) break;
            const bool silent = (bufferFlags & AUDCLNT_BUFFERFLAGS_SILENT) != 0 || data == nullptr;
            for (UINT32 i = 0; i < frames; ++i) {
                float mono = 0;
                if (!silent) {
                    const uint8_t* frame = data + static_cast<size_t>(i) * fmt.blockAlign;
                    const int bytesPerSample = fmt.bits / 8;
                    for (int c = 0; c < fmt.channels; ++c) mono += readSample(frame + c * bytesPerSample, fmt);
                    mono /= static_cast<float>(fmt.channels);
                }
                resampler.push(mono, out);
            }
            reader->ReleaseBuffer(frames);
            gotData = true;
            hr = reader->GetNextPacketSize(&packet);
        }
        if (FAILED(hr)) {
            // Most often AUDCLNT_E_DEVICE_INVALIDATED: the device was unplugged or the default changed.
            logmsg("stream lost (0x%08lx); reattaching", static_cast<unsigned long>(hr));
            client->Stop();
            return Result::Reattach;
        }

        emit(out.data(), out.size());
        emitted += out.size();
        out.clear();

        // Loopback delivers nothing while nothing is playing, but listen.py ends an utterance by
        // counting quiet frames, so a silent gap must still arrive as samples. Pad with zeros up to
        // wall-clock time; while real audio flows this adds nothing.
        if (!gotData) {
            LARGE_INTEGER now;
            QueryPerformanceCounter(&now);
            const double seconds = static_cast<double>(now.QuadPart - start.QuadPart) / static_cast<double>(freq.QuadPart);
            const int64_t expected = static_cast<int64_t>(seconds * kOutRate);
            const int64_t deficit = expected - static_cast<int64_t>(emitted);
            if (deficit >= kOutRate / 100) {  // at least 10 ms
                const size_t n = static_cast<size_t>(deficit > kOutRate ? kOutRate : deficit);
                zeros.assign(n, 0.0f);
                emit(zeros.data(), n);
                emitted += n;
            }
        }

        // The default device can change without this stream erroring (e.g. headphones plugged in).
        if (GetTickCount64() - lastDeviceCheck >= 1000) {
            lastDeviceCheck = GetTickCount64();
            Com<IMMDevice> current;
            if (SUCCEEDED(enumerator->GetDefaultAudioEndpoint(flow, eConsole, &current))) {
                LPWSTR currentId = nullptr;
                current->GetId(&currentId);
                const bool same = currentId && deviceId == currentId;
                CoTaskMemFree(currentId);
                if (!same) {
                    logmsg("default %s device changed; reattaching", what);
                    client->Stop();
                    return Result::Reattach;
                }
            }
        }

        Sleep(10);
    }
}

// MARK: main

int main(int argc, char** argv) {
    const std::string source = argc > 1 ? argv[1] : "system";
    EDataFlow flow;
    if (source == "system") flow = eRender;
    else if (source == "mic") flow = eCapture;
    else {
        logmsg("usage: audiotap system|mic");
        return 64;
    }

    timeBeginPeriod(1);  // 1 ms timer, so Sleep(10) really is about 10 ms
    HRESULT hr = CoInitializeEx(nullptr, COINIT_MULTITHREADED);
    if (FAILED(hr)) {
        logmsg("COM start-up failed (0x%08lx)", static_cast<unsigned long>(hr));
        return 1;
    }
    Com<IMMDeviceEnumerator> enumerator;
    hr = CoCreateInstance(__uuidof(MMDeviceEnumerator), nullptr, CLSCTX_ALL, __uuidof(IMMDeviceEnumerator),
                          reinterpret_cast<void**>(&enumerator));
    if (FAILED(hr)) {
        logmsg("cannot create the device enumerator (0x%08lx)", static_cast<unsigned long>(hr));
        return 1;
    }

    for (;;) {
        if (capture(enumerator, flow) == Result::Fatal) return 1;
        Sleep(1000);  // reattach: the device can vanish for a moment
    }
}