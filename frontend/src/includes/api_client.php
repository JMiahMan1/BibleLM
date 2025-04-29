<?php
/**
 * Fetches data from the backend API.
 *
 * @param string $endpoint The API endpoint path (e.g., '/api/sources/').
 * @param string $method The HTTP method (e.g., 'GET', 'POST').
 * @param array|null $data Data to send for POST/PUT requests.
 * @return array|null Decoded JSON response or null on error.
 */
function fetchDataFromApi(string $endpoint, string $method = 'GET', ?array $data = null): ?array {
    // --- IMPORTANT: Replace with your actual backend URL ---
    // If backend runs in another Docker container named 'backend', use:
    // $baseUrl = 'http://backend:8000'; // Default FastAPI port is 8000
    // If running backend locally for testing frontend outside Docker:
    $baseUrl = getenv('BACKEND_API_URL') ?: 'http://localhost:8000'; // Use environment variable or default

    $url = rtrim($baseUrl, '/') . '/' . ltrim($endpoint, '/');

    $options = [
        'http' => [
            'method' => $method,
            'header' => "Content-Type: application/json\r\n" .
                        "Accept: application/json\r\n",
            'ignore_errors' => true, // Prevent file_get_contents from throwing warnings on 4xx/5xx errors
            'timeout' => 10, // Timeout in seconds
        ],
        // If you need SSL verification (recommended for production)
        // 'ssl' => [
        //     'verify_peer' => true,
        //     'verify_peer_name' => true,
        //     // Add path to CA certificate bundle if needed
        //     // 'cafile' => '/path/to/cacert.pem',
        // ]
    ];

    if ($data !== null && ($method === 'POST' || $method === 'PUT')) {
        $options['http']['content'] = json_encode($data);
        $options['http']['header'] .= "Content-Length: " . strlen($options['http']['content']) . "\r\n";
    }

    $context = stream_context_create($options);
    $response = @file_get_contents($url, false, $context); // Use @ to suppress errors if needed, check $response === false

    if ($response === false) {
        // Handle connection error - log it, return null, etc.
        error_log("API call failed for endpoint: " . $endpoint);
        return null;
    }

    // Get HTTP status code from headers
    $statusCode = 0;
    if (isset($http_response_header) && is_array($http_response_header) && count($http_response_header) > 0) {
        sscanf($http_response_header[0], 'HTTP/%*d.%*d %d', $statusCode);
    }


    $decoded = json_decode($response, true);

    // Check if JSON decoding failed or if it's an error status code
    if (json_last_error() !== JSON_ERROR_NONE || $statusCode >= 400) {
         error_log("API Error ($statusCode) for $endpoint: " . $response);
         // You might want to return the status code or error message here too
         return null;
    }


    return $decoded;
}
?>
