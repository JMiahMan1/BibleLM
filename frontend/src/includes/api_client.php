<?php
/**
 * Fetches data from the backend API.
 *
 * @param string $endpoint The API endpoint path (e.g., '/api/sources/').
 * @param string $method The HTTP method (e.g., 'GET', 'POST', 'PUT', 'DELETE').
 * @param array|null $data Data to send for POST/PUT requests.
 * @return array|null Decoded JSON response or null on error.
 */
function fetchDataFromApi(string $endpoint, string $method = 'GET', ?array $data = null): ?array {
    // --- IMPORTANT: Replace with your actual backend URL ---
    // If backend runs in another Docker container named 'backend', use:
    // $baseUrl = 'http://backend:8000'; // Default FastAPI port is 8000
    // If running backend locally for testing frontend outside Docker:
    $baseUrl = getenv('BACKEND_API_URL') ?: 'http://172.17.0.1:8000'; // Use environment variable or default

    $url = rtrim($baseUrl, '/') . '/' . ltrim($endpoint, '/');

    $options = [
        'http' => [
            'method' => $method,
            'header' => "Content-Type: application/json\r\n" .
                        "Accept: application/json\r\n",
            'ignore_errors' => true, // Prevent file_get_contents from throwing warnings on 4xx/5xx errors
            'timeout' => 15, // Timeout in seconds (Increased timeout)
        ],
        // If you need SSL verification (recommended for production)
        // 'ssl' => [
        //     'verify_peer' => true,
        //     'verify_peer_name' => true,
        //     // Add path to CA certificate bundle if needed
        //     // 'cafile' => '/path/to/cacert.pem',
        // ]
    ];

    if ($data !== null && ($method === 'POST' || $method === 'PUT' || $method === 'PATCH')) {
        $options['http']['content'] = json_encode($data);
        // Content-Length header is often added automatically by PHP streams,
        // but explicitly adding it can sometimes help. Be cautious as it might
        // cause issues if the content is large or streamed. Removing for simplicity.
        // $options['http']['header'] .= "Content-Length: " . strlen($options['http']['content']) . "\r\n";
    }

    // Use @ to suppress file_get_contents warnings on failure, check return value instead
    $context = stream_context_create($options);
    $response = @file_get_contents($url, false, $context);


    if ($response === false) {
        // Handle connection or low-level network error
        error_log("API call failed for endpoint: " . $endpoint . " - Network or connection error.");
        return null;
    }

    // Get HTTP status code from headers if available
    $statusCode = 0;
    if (isset($http_response_header) && is_array($http_response_header) && count($http_response_header) > 0) {
        // The first header line contains the status code, e.g., "HTTP/1.1 200 OK"
        preg_match('/HTTP\/\d\.\d\s+(\d+)/', $http_response_header[0], $matches);
        if (isset($matches[1])) {
            $statusCode = (int)$matches[1];
        }
    }

    $decoded = json_decode($response, true);

    // Check if JSON decoding failed OR if the status code indicates an error
    if ($decoded === null && json_last_error() !== JSON_ERROR_NONE) {
        error_log("API call to $endpoint received invalid JSON response. Status Code: $statusCode. Raw response: " . $response);
         // Optionally, return an error indicator or the raw response
         return null;
    }

    // Also treat 4xx and 5xx status codes as errors, even if JSON is valid
    if ($statusCode >= 400) {
         error_log("API Error ($statusCode) for $endpoint. Response: " . $response);
         // You might want to return an array indicating the error and status code
         // return ['error' => true, 'statusCode' => $statusCode, 'response' => $decoded ?? $response];
         return null; // Return null for error for simplicity
    }


    return $decoded;
}

/**
 * Creates a new chat session.
 *
 * @param string $title The title for the new session.
 * @param array $documentIds List of document IDs to link to the session.
 * @return array|null The created session data or null on error.
 */
function createChatSession(string $title, array $documentIds = []): ?array {
    $endpoint = '/api/sessions';
    $method = 'POST';
    $data = [
        'title' => $title,
        'document_ids' => $documentIds
    ];
    return fetchDataFromApi($endpoint, $method, $data);
}

/**
 * Gets a list of all chat sessions.
 *
 * @return array|null A list of session data or null on error.
 */
function getChatSessions(): ?array {
    $endpoint = '/api/sessions';
    $method = 'GET';
    return fetchDataFromApi($endpoint, $method);
}

/**
 * Gets details for a specific chat session.
 *
 * @param int $sessionId The ID of the session.
 * @return array|null The session data or null on error.
 */
function getChatSessionDetails(int $sessionId): ?array {
    $endpoint = "/api/sessions/{$sessionId}";
    $method = 'GET';
    return fetchDataFromApi($endpoint, $method);
}

/**
 * Gets messages for a specific chat session.
 *
 * @param int $sessionId The ID of the session.
 * @return array|null A list of message data or null on error.
 */
function getChatSessionMessages(int $sessionId): ?array {
    $endpoint = "/api/sessions/{$sessionId}/messages";
    $method = 'GET';
    return fetchDataFromApi($endpoint, $method);
}

/**
 * Sends a user message to a chat session and gets the RAG response.
 *
 * @param int $sessionId The ID of the session.
 * @param string $question The user's question.
 * @param array $documentIds List of document IDs to ground the query on.
 * @return array|null The chat response data (assistant's answer) or null on error.
 */
function sendChatMessage(int $sessionId, string $question, array $documentIds = []): ?array {
    // This endpoint is for sending a user query and getting a RAG response
    $endpoint = '/api/query';
    $method = 'POST';
    $data = [
        'session_id' => $sessionId,
        'question' => $question,
        'document_ids' => $documentIds
    ];
     // The backend /api/query endpoint will add the user message and assistant reply to history
    return fetchDataFromApi($endpoint, $method, $data);
}


// You might also need functions for:
// - Uploading files (frontend JS likely handles this with progress updates)
// - Ingesting URLs
// - Getting document list/details
// - Getting document processing status
// - Generating summaries (frontend JS likely handles this with WS updates)
// - Downloading files

// Example: Function to get document list (already exists in backend main.py)
function getDocumentsList(): ?array {
    $endpoint = '/documents';
    $method = 'GET';
    return fetchDataFromApi($endpoint, $method);
}

// Example: Function to get document status (already exists)
function getDocumentStatus(int $docId): ?array {
     $endpoint = "/status/{$docId}";
     $method = 'GET';
     return fetchDataFromApi($endpoint, $method);
}

?>
