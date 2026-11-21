# Teaching with Murmury

For instructors of software engineering and open source courses who want their students to contribute to
a real project, with real code review, during the term.

## What your students get

- **A real, readable code base.** Murmury is a desktop app that listens to a call, transcribes it locally
  and answers questions from the user's documents. It is written in Python (PySide6, pytest), small enough
  to read in a few days, and has 336 automated tests.
- **Issues sized for a course.** Every issue is labelled `level 1` (small: usually a set of tests),
  `level 2` (moderate) or `level 3` (substantial: a feature or part of the Windows port), and says which
  files to touch and when it is done. Many need no Mac: tests, answer evals, and Windows and Linux work.
- **Real code review.** The maintainer reads every pull request in full, runs it against the latest
  `main` before merging, and says in the review exactly what to change and why. The merge comment says what
  was tested.
- **Work that lasts.** Merged code ships in the app and stays in the public history under the student's
  name.

[LEARNING.md](LEARNING.md) describes the four tracks (tests, answer evals, desktop features, the Windows
port), what each one teaches and which files to read first.

## How it works

1. **Write before the term starts**, ideally four weeks ahead: open a
   [Discussion](https://github.com/GianlucaBave/murmury/discussions) or an issue, or email
   murmuryelf@gmail.com. Tell us how many students, their level, the dates and how much time they have.
2. **We reserve a set of issues** for your course and label them `course:<name>`, so your students find
   them easily and nobody else takes them. We write new ones if needed.
3. **Students sign the CLA first**: one click with their GitHub account, on
   [CLA Assistant](https://cla-assistant.io/GianlucaBave/murmury). The email on their commits must belong
   to their GitHub account, or the check blocks the merge.
4. **Students claim an issue with a short plan** in a comment: what they will change and how they will test
   it. We assign it, usually within a day.
5. **Students open a pull request**, usually within a week of being assigned. Reviews come within a few
   days; students address the feedback and update the pull request until it is merged.

## What we ask

- One issue per student at a time, so everyone gets one.
- Every contributor signs the [Contributor License Agreement](docs/CLA.md). Students keep the copyright of
  their work.
- The code stays in this repository under GPL-3.0.
- Students should understand and be able to explain their change; AI-assisted work is welcome on that
  condition ([CONTRIBUTING.md](CONTRIBUTING.md) has the details).

Students can also start on their own, without a reserved set: "Your first pull request in 30 minutes" in
[CONTRIBUTING.md](CONTRIBUTING.md) takes them from clone to pull request.
