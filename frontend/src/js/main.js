document.addEventListener('DOMContentLoaded', () => {
    const sourceList = document.getElementById('source-list');
    const mainContent = document.getElementById('main-content');
    const chatBody = document.getElementById('chat-body');
    const chatInput = document.getElementById('chat-input');
    const sendButton = document.getElementById('send-button');
    const mainContainer = document.querySelector('.main-container'); // Get container for chat ID

    // --- Configuration ---
    // Get base URL from environment or default (should match PHP)
    const backendApiUrl = window.BACKEND_API_URL || 'http://localhost:8000';

    // --- Event Listeners ---

    // 1. Click on a Source Item
    if (sourceList) {
        sourceList.addEventListener('click', async (event) => {
            const listItem = event.target.closest('li[data-source-id]');
            if (!listItem) return; // Clicked outside a valid list item

            const sourceId = listItem.dataset.sourceId;
            console.log(`Source clicked: ${sourceId}`);

            // Remove active class from other items
            sourceList.querySelectorAll('li.active').forEach(li => li.classList.remove('active'));
            // Add active class to clicked item
            listItem.classList.add('active');

            // --- Example: Fetch source details and display in chat (replace/extend as needed) ---
            // This is just a basic example. You'll likely want a more sophisticated
            // way to handle source selection and its effect on the chat.
            // Maybe it adds the source to the current chat context, or opens a detail view.
            try {
                const response = await fetch(`${backendApiUrl}/api/sources/${sourceId}`);
                if (!response.ok) {
                    throw new Error(`HTTP error! status: ${response.status}`);
                }
                const sourceData = await response.json();

                // Example: Append a message to chat showing source title (replace with actual UI update)
                if (chatBody) {
                    const infoMessage = document.createElement('div');
                    infoMessage.classList.add('chat-message', 'system-message'); // Add a class for styling system info
                    infoMessage.innerHTML = `<p><strong>Source Selected:</strong> ${sourceData.title || 'Unknown Title'}</p><p><small>ID: ${sourceId}</small></p>`;
                     // Add a simple style for system messages if needed in CSS:
                     // .system-message { background-color: #f0f0f0; color: #555; font-style: italic; text-align: center; max-width: 100%; margin-left: 0; }
                    chatBody.appendChild(infoMessage);
                    chatBody.scrollTop = chatBody.scrollHeight; // Scroll to bottom
                }

            } catch (error) {
                console.error("Error fetching source details:", error);
                // Display error to user (e.g., in a notification area)
                if (chatBody) {
                     const errorMessage = document.createElement('div');
                     errorMessage.classList.add('chat-message', 'system-message', 'error-message');
                     errorMessage.innerHTML = `<p>Error loading details for source ${sourceId}.</p>`;
                     // Add .error-message { color: red; } to CSS
                     chatBody.appendChild(errorMessage);
                     chatBody.scrollTop = chatBody.scrollHeight;
                }
            }
        });
    }

    // 2. Send Chat Message
    const sendMessage = async () => {
        const messageText = chatInput.value.trim();
        const currentChatId = mainContainer?.dataset.currentChatId; // Get chat ID from data attribute

        if (!messageText || !currentChatId) {
            console.log("Cannot send empty message or chat ID missing.");
            return; // Don't send empty messages or if chat ID is missing
        }

        // Add user message immediately to UI (Optimistic Update)
        appendMessage(messageText, 'user');
        const userMessageText = messageText; // Store before clearing
        chatInput.value = ''; // Clear input
        adjustTextareaHeight(chatInput); // Reset height

        try {
            const response = await fetch(`${backendApiUrl}/api/chats/${currentChatId}/messages/`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Accept': 'application/json',
                },
                body: JSON.stringify({
                    content: userMessageText,
                    // role: 'user' // Backend should ideally set/know the role
                }),
            });

            if (!response.ok) {
                 // Handle non-OK responses (e.g., 4xx, 5xx)
                 const errorData = await response.json().catch(() => ({ detail: 'Failed to send message. Unknown error.' })); // Try to parse error
                 throw new Error(`HTTP error ${response.status}: ${errorData.detail || response.statusText}`);
            }

            const responseData = await response.json();

            // Assuming the response contains the assistant's reply
            // Adjust based on your actual API response structure
            if (responseData && responseData.content) { // Check if responseData itself is the message or contains it
                 // If the POST request *itself* returns the assistant's reply directly:
                 appendMessage(responseData.content, responseData.role || 'assistant');
            } else {
                 // If you need to make *another* request to get the assistant's reply, do it here.
                 // This often happens with streaming responses or background processing.
                 console.log("Message sent, waiting for assistant reply (implement polling or WebSocket if needed).");
                 // For now, just log success or add a placeholder
                 // appendMessage("Assistant is thinking...", 'assistant-placeholder');
            }

        } catch (error) {
            console.error("Error sending message:", error);
            // Display error to user, maybe revert optimistic update or show error state
            appendMessage(`Error: ${error.message}`, 'system-message error-message');
        }
    };

    if (sendButton && chatInput) {
        sendButton.addEventListener('click', sendMessage);

        chatInput.addEventListener('keypress', (event) => {
            // Send on Enter key, but allow Shift+Enter for new line
            if (event.key === 'Enter' && !event.shiftKey) {
                event.preventDefault(); // Prevent default Enter behavior (new line)
                sendMessage();
            }
        });

        // Auto-resize textarea
        chatInput.addEventListener('input', () => adjustTextareaHeight(chatInput));
        adjustTextareaHeight(chatInput); // Initial adjustment
    }

    // --- Helper Functions ---

    function appendMessage(text, role = 'user') {
        if (!chatBody) return;
        const messageDiv = document.createElement('div');
        messageDiv.classList.add('chat-message');
        // Add role-specific class
        if (role === 'assistant') {
            messageDiv.classList.add('assistant-message');
        } else if (role === 'user') {
            messageDiv.classList.add('user-message');
        } else { // For system info, errors, etc.
             messageDiv.classList.add(role); // e.g., 'system-message', 'error-message'
        }

        // Sanitize text before inserting as HTML (basic example)
        // For robust sanitization, use a library like DOMPurify if dealing with complex/untrusted HTML
        const paragraph = document.createElement('p');
        paragraph.textContent = text; // Use textContent to prevent XSS
        messageDiv.appendChild(paragraph);


        chatBody.appendChild(messageDiv);
        chatBody.scrollTop = chatBody.scrollHeight; // Scroll to the bottom
    }

    function adjustTextareaHeight(textarea) {
        textarea.style.height = 'auto'; // Temporarily shrink to recalculate scrollHeight
        textarea.style.height = `${textarea.scrollHeight}px`; // Set to calculated height
    }

    // --- Initial Setup ---
    // e.g., Set initial scroll position for chat
    if (chatBody) {
        chatBody.scrollTop = chatBody.scrollHeight;
    }

    // Add more event listeners for other buttons (Add Note, Generate, etc.)
    // These would likely call specific functions that make fetch requests
    // to the corresponding backend endpoints (e.g., /api/notes/, /api/studio/generate)

});
