# Frontend Setup (Next.js Example)

1.  **Initialize Next.js:**
    ```bash
    npx create-next-app@latest frontend --typescript --tailwind --eslint --app --src-dir --import-alias "@/*"
    cd frontend
    ```

2.  **Install Dependencies:**
    * `axios` or use `Workspace` for API calls.
    * A state management library (optional but recommended for complexity): `zustand`, `jotai`, or `@reduxjs/toolkit`.
    * Libraries for UI components (optional): `@headlessui/react`, `radix-ui`, etc.
    * Date formatting: `date-fns` or `dayjs`.
    * File upload handling (optional, can use native input): `react-dropzone`.
    * WebSocket client (if using WebSockets): `socket.io-client` or native `WebSocket`.

    ```bash
    npm install axios zustand date-fns react-dropzone socket.io-client
    # or
    yarn add axios zustand date-fns react-dropzone socket.io-client
    ```

3.  **Develop Components:**
    * Create pages/components for:
        * Dashboard/Layout
        * File Upload Area (`react-dropzone`)
        * URL Input Form
        * Document List (fetching from `/documents`)
        * Task Status Indicator (polling `/status/{doc_id}` or using WebSockets)
        * Chat Interface (sending to `/chat`, displaying responses and sources)
        * Summary Request Form (sending to `/summary`)
        * Download Links (pointing to `/download/{type}/{filename}`)
    * Use TailwindCSS for styling.
    * Implement API calls to the backend (running on port 8000). Remember to handle loading states and errors.
    * Implement logic for selecting documents for chat/summary.
    * Implement real-time updates via polling or WebSockets.

4.  **Environment Variables:**
    * Set `NEXT_PUBLIC_API_URL=http://localhost:8000` (or the appropriate URL when running in Docker) in a `.env.local` file.

5.  **Build:**
    ```bash
    npm run build
    # or
    yarn build
    ```
