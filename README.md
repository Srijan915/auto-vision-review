# ClaimSense Visualizer

Build ClaimSense, a vehicle insurance AI damage reviewer frontend in React, TypeScript, and Tailwind.

Key Requirements:
- Automotive diagnostic / engineering aesthetic: graphite dark surfaces, warm off-white content areas, restrained steel-blue accents, crisp technical typography, subtle micro-interactions.
- Workspaces / views: Dashboard, Review Queue, Assessment Detail, Evidence Center, Human Review modal/panel, and Audit History.
- Assessment Detail:
  - Vehicle assessment images rendered with scaled YOLO damage bounding boxes (bounding boxes scaled accurately from image native dimensions), detected damage class, and confidence score.
  - Provisional severity strictly limited to Minor, Moderate, or Severe.
  - human_review_required status badge.
  - Retrieved evidence section with source, title, type, and legal/technical disclaimer.
  - Gemini explanation when available.
  - Human decision capture (Accept / Reject / Request Re-inspection / Adjust Severity with notes).
  - Review history timeline and audit events log.
- API Client & Data:
  - Typed API client targeting FastAPI backend using `VITE_API_BASE_URL` with endpoints:
    - POST /assessments
    - GET /assessments/{assessment_id}
    - PUT /assessments/{assessment_id}/review
  - Built-in realistic fixture toggle so the app is fully functional and interactive out of the box without requiring a live backend.
  - Strict scope: NEVER add or display insurance coverage, payouts, repair costs, repair-vs-replace calculations, vehicle valuation, fraud scores, liability assignment, or autonomous approval/rejection. Human review remains strictly mandatory. Frontend only.
- Polished upload flow (drag and drop assessment images), loading skeletons, error handling, empty states, responsive layouts, and accessible controls.

This project was built with [Lovable](https://lovable.dev).

## Build with Lovable

Continue developing this project in the [Lovable editor](https://lovable.dev/projects/a05f81a8-053c-41a8-abe7-e582ce70611c).

- **Ship faster**: describe what you want to build and Lovable handles the code.
- **Stay in sync**: every change made in Lovable is committed straight to this repository.
- **Full ownership**: this code is yours. Push to `main` on GitHub and your changes sync back into Lovable, ready for your next prompt.

## Development

Prefer working locally? You need Node.js and npm — [install with nvm](https://github.com/nvm-sh/nvm#installing-and-updating).

```sh
git clone <this-repository-url>
cd <repository-name>
npm i
npm run dev
```
