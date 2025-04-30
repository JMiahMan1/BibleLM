// frontend/src/js/main.js

// Ensure this is set correctly by the PHP backend (e.g., http://192.168.2.211:8000)
const backendApiUrl = window.BACKEND_API_URL;

// DOM Elements - Define them inside DOMContentLoaded
let chatSessionsList;
let chatWindow;
let messagesContainer;
let messageInput;
let sendMessageBtn;
let newChatBtn;
let documentListContainer;
let documentsList;
let documentStatusContainer;


// State variables
let currentChatSessionId = null;
let selectedDocumentIds = []; // Array to store IDs of documents selected for grounding the current chat session


// --- Helper Functions ---

// Corrected appendMessage function: Adds messages to the UI
function appendMessage(role, content, sourceDocuments = []) {
    // Use the variables defined and assigned inside DOMContentLoaded
    const messagesContainer = document.getElementById('messages-container'); // Redefine or ensure scope is correct

    const messageElement = document.createElement('div');
    // Add base class and role-specific class using separate arguments to classList.add
    // Example: role 'user' -> classes 'chat-message', 'user-message'
    messageElement.classList.add('chat-message', `${role}-message`);

    // Optional: Add a specific class for system messages that represent errors
    // This assumes system messages starting with "Error:" are error indicators
    if (role === 'system' && content.startsWith('Error:')) {
        messageElement.classList.add('error-message'); // Add 'error-message' as a distinct class
        console.error(`System Error Message Displayed: ${content}`); // Log system errors
    } else {
        console.log(`Appending Message: Role - ${role}, Content - "${content.substring(0, 100)}..."`); // Log non-error messages
    }

    const contentElement = document.createElement('div');
    contentElement.classList.add('message-content');
    // Use innerHTML and replace line breaks with <br> for displaying multi-line content
    contentElement.innerHTML = content.replace(/\n/g, '<br>');

    messageElement.appendChild(contentElement);

    // Add source documents list if provided (typically for assistant messages)
    // Check if sourceDocuments is an array and is not empty
    if (Array.isArray(sourceDocuments) && sourceDocuments.length > 0) {
        const sourcesElement = document.createElement('div');
        sourcesElement.classList.add('message-sources');
        sourcesElement.innerHTML = '<strong>Sources:</strong> ';
        // Map document objects to their filenames and join them with a comma
        const sourceList = sourceDocuments.map(doc => doc.filename).join(', ');
        sourcesElement.innerHTML += sourceList;
        messageElement.appendChild(sourcesElement);
    }

    // Add the completed message element to the messages container
    if (messagesContainer) { // Check if messagesContainer was found
        messagesContainer.appendChild(messageElement);

        // Scroll the messages container to the bottom to show the latest message
        messagesContainer.scrollTop = messagesContainer.scrollHeight;
    } else {
        console.error("messagesContainer not found when attempting to append message.");
    }
}


// Function to load existing chat sessions from the backend
async function loadChatSessions() {
    console.log('Attempting to load chat sessions from:', `${backendApiUrl}/api/sessions`);
    try {
        const response = await fetch(`${backendApiUrl}/api/sessions`);
        if (!response.ok) {
            // If response is not OK (e.g., 400, 500), try to read error details
            const errorData = await response.json().catch(() => ({ detail: response.statusText })); // Handle cases where response is not JSON
            console.error('Failed to load chat sessions:', response.status, errorData);
            // Display an error message in the chat window using appendMessage
             appendMessage('system', `Error loading sessions: ${response.status} - ${errorData.detail || JSON.stringify(errorData)}`);
            return; // Stop execution after logging/displaying error
        }

        const sessions = await response.json();
        console.log('Successfully loaded chat sessions:', sessions);

        // Clear the current list of chat sessions in the UI
        if (chatSessionsList) { // Check if element was found
             chatSessionsList.innerHTML = '';

            // Populate the UI list with loaded sessions
            sessions.forEach(session => {
                const sessionElement = document.createElement('li');
                sessionElement.classList.add('chat-session-item');
                sessionElement.dataset.sessionId = session.id; // Store session ID on the element
                sessionElement.textContent = session.title; // Display session title
                // Add click event listener to switch to this session
                sessionElement.addEventListener('click', () => switchChatSession(session.id));
                chatSessionsList.appendChild(sessionElement); // Add to the list
            });
        } else {
             console.error("chatSessionsList element not found.");
        }


        // If sessions were loaded and no session is currently selected, automatically select the first one
        if (sessions.length > 0 && currentChatSessionId === null) {
            switchChatSession(sessions[0].id);
        } else if (sessions.length > 0 && currentChatSessionId !== null) {
             // If sessions were loaded and a session was already selected (e.g., on refresh), re-select it
             // This ensures the selected state in the UI is correct
             if (chatSessionsList) { // Check if element was found
                 const selectedElement = chatSessionsList.querySelector(`.chat-session-item[data-session-id="${currentChatSessionId}"]`);
                 if (selectedElement) {
                      selectedElement.classList.add('selected');
                 } else {
                     // If the previously selected session doesn't exist anymore, switch to the first one
                     switchChatSession(sessions[0].id);
                 }
             }
        } else if (sessions.length === 0) {
             // If no sessions were loaded, clear the current session state
             currentChatSessionId = null;
             if (messagesContainer) messagesContainer.innerHTML = ''; // Clear messages area
             appendMessage('system', 'No chat sessions found. Click "+ New Chat" to create one.');
             // Disable message input if no session
             if (messageInput) messageInput.disabled = true;
             if (sendMessageBtn) sendMessageBtn.disabled = true;
        }


    } catch (error) {
        // This catch block handles network errors (e.g., ERR_CONNECTION_REFUSED)
        console.error('Network or server error loading chat sessions:', error);
         appendMessage('system', 'Error: Could not load chat sessions due to network or server connection issue.');
         // Disable message input if connection fails
         if (messageInput) messageInput.disabled = true;
         if (sendMessageBtn) sendMessageBtn.disabled = true;
    }
}

// Function to create a new chat session on the backend
async function createNewChatSession() {
    // Prompt user for a title
    const chatTitle = prompt("Enter a title for the new chat session:");
    if (!chatTitle) {
        console.log("New chat session creation cancelled by user.");
        return; // Exit the function if user cancels the prompt or enters empty string
    }

    // Get the IDs of currently selected documents from the documents list
    // These documents will be initially linked to the new chat session
    const selectedDocumentIdsForNewSession = getSelectedDocumentIds();
    console.log(`Attempting to create new chat session with title: "${chatTitle}" and initial document IDs: ${selectedDocumentIdsForNewSession}`);

    try {
        // Send POST request to backend to create the session
        const response = await fetch(`${backendApiUrl}/api/sessions`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json', // Specify content type as JSON
            },
            body: JSON.stringify({ // Convert the data object to a JSON string
                title: chatTitle,
                document_ids: selectedDocumentIdsForNewSession // Include selected document IDs in the request body
            })
        });

        if (!response.ok) {
            // If response is not OK (e.g., 400, 422, 500), read error details
            const errorData = await response.json().catch(() => ({ detail: response.statusText })); // Handle non-JSON error responses
            console.error('Failed to create chat session:', response.status, errorData);
            // Display a system message with error details
            appendMessage('system', `Error creating session: ${response.status} - ${errorData.detail || JSON.stringify(errorData)}`);
            return; // Stop execution
        }

        // If session creation is successful (e.g., 201 Created)
        const newSession = await response.json(); // Parse the JSON response body
        console.log('Successfully created new chat session:', newSession);

        // Reload the list of chat sessions to include the newly created one
        await loadChatSessions();

        // Automatically switch to the new session
        switchChatSession(newSession.id);

    } catch (error) {
        // This catch block handles network errors during the fetch call
        console.error('Network or server error creating chat session:', error);
        appendMessage('system', 'Error: Could not create chat session due to network or server connection issue.');
    }
}

// Function to switch to a different chat session (updates UI state)
async function switchChatSession(sessionId) {
    console.log('Switching to chat session:', sessionId);
    // Update the state variable tracking the currently active session
    currentChatSessionId = sessionId;

    // Update the UI to visually indicate the selected session
    if (chatSessionsList) { // Check if element was found
         document.querySelectorAll('.chat-session-item').forEach(item => {
            item.classList.remove('selected'); // Remove 'selected' class from all items
            if (parseInt(item.dataset.sessionId) === sessionId) {
                item.classList.add('selected'); // Add 'selected' class to the clicked item
            }
        });
    } else {
         console.error("chatSessionsList element not found during switch.");
    }


    // Clear the message area before loading messages for the new session
    if (messagesContainer) messagesContainer.innerHTML = '';
    // Display a system message indicating the session change
    // Optionally, fetch the session title to display here if not already available
    let sessionTitle = `Session ${sessionId}`;
     if (chatSessionsList) { // Check if element was found
        const sessionTitleElement = chatSessionsList.querySelector(`.chat-session-item[data-session-id="${sessionId}"]`);
        sessionTitle = sessionTitleElement ? sessionTitleElement.textContent : `Session ${sessionId}`;
     } else {
          console.error("chatSessionsList element not found when getting title during switch.");
     }

    appendMessage('system', `Switched to "${sessionTitle}"`);

    // Fetch and display existing messages for this session
    await loadChatMessages(sessionId);

    // Fetch and load documents associated with this session
    await loadSessionDocuments(sessionId); // This will also update selectedDocumentIds and UI

    // Enable message input and send button now that a session is active
    if (messageInput) messageInput.disabled = false;
    if (sendMessageBtn) sendMessageBtn.disabled = false;
    if (messageInput) messageInput.focus(); // Set focus to the input field
}

// Function to load chat messages for a specific session from the backend
async function loadChatMessages(sessionId) {
    console.log('Attempting to load messages for session:', sessionId, 'from:', `${backendApiUrl}/api/sessions/${sessionId}/messages`);
    try {
        // Fetch messages for the given session ID
        const response = await fetch(`${backendApiUrl}/api/sessions/${sessionId}/messages`);
        if (!response.ok) {
            const errorData = await response.json().catch(() => ({ detail: response.statusText }));
            console.error('Failed to load messages:', response.status, errorData);
             appendMessage('system', `Error loading messages: ${response.status} - ${errorData.detail || JSON.stringify(errorData)}`);
            return;
        }

        const messages = await response.json();
        console.log('Successfully loaded messages for session', sessionId, ':', messages);

        // Display loaded messages in the chat window
        messages.forEach(message => {
            // Call appendMessage for each loaded message
            // Note: Source documents are not currently stored directly with messages in the backend schema.
            // The RAG query response includes source documents separately.
            // Pass an empty array for sourceDocuments here based on the current schema.
            appendMessage(message.role, message.content, []); // Append message with role and content
        });

    } catch (error) {
        console.error('Network or server error loading messages:', error);
         appendMessage('system', 'Error: Could not load messages due to network or server connection issue.');
    }
}

// Function to load documents linked to a specific session from the backend
async function loadSessionDocuments(sessionId) {
     console.log('Attempting to load documents for session:', sessionId, 'from:', `${backendApiUrl}/api/sessions/${sessionId}`);
     try {
         // Fetch session details, which include linked documents based on the backend schema
         const response = await fetch(`${backendApiUrl}/api/sessions/${sessionId}`);
         if (!response.ok) {
             const errorData = await response.json().catch(() => ({ detail: response.statusText }));
             console.error('Failed to load session documents:', response.status, errorData);
             appendMessage('system', `Error loading session documents: ${response.status} - ${errorData.detail || JSON.stringify(errorData)}`);
             // If loading fails, clear the list of selected documents for this session in the frontend state
             selectedDocumentIds = [];
             updateDocumentSelectionUI(); // Update UI to show no documents selected
             return;
         }

         const sessionDetails = await response.json();
         console.log('Successfully loaded session details (including documents):', sessionDetails.documents);

         // Update the frontend state variable with the IDs of documents linked to this session
         selectedDocumentIds = sessionDetails.documents.map(doc => doc.id);

         // Update the visual state of the document list UI based on the selectedDocumentIds
         updateDocumentSelectionUI();

     } catch (error) {
         console.error('Network or server error loading session documents:', error);
         appendMessage('system', 'Error: Could not load session documents due to network or server connection issue.');
          // If loading fails, clear selected documents and update UI
         selectedDocumentIds = [];
         updateDocumentSelectionUI();
     }
}


// Function to send a message/query to the backend API
async function sendChatMessage() {
    const userQuestion = messageInput.value.trim(); // Get user input, trim whitespace
    // Do not send empty messages or if no chat session is currently selected
    if (userQuestion === '' || currentChatSessionId === null) {
        console.warn("Attempted to send empty message or no session selected.");
        return; // Exit the function
    }

    // Append the user's message to the chat window immediately for responsiveness
    appendMessage('user', userQuestion);
    messageInput.value = ''; // Clear the input field after sending

    // Disable input and send button while waiting for backend response
    if (messageInput) messageInput.disabled = true;
    if (sendMessageBtn) sendMessageBtn.disabled = true;

    // Get the relevant document IDs for grounding the query
    // Use the documents currently linked to the session
    console.log('Attempting to send message to session:', currentChatSessionId, 'with grounding documents:', selectedDocumentIds, 'Question:', userQuestion);


    try {
        // Send POST request to the backend's query endpoint
        const response = await fetch(`${backendApiUrl}/api/query`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json', // Indicate the content is JSON
            },
            body: JSON.stringify({ // Convert the data object to a JSON string
                session_id: currentChatSessionId, // Include the current session ID
                question: userQuestion, // Include the user's question
                document_ids: selectedDocumentIds // Include the IDs of documents selected for grounding
            })
        });

        if (!response.ok) {
            // If response is not OK (e.g., 400, 422, 500), read error details
            const errorData = await response.json().catch(() => ({ detail: response.statusText })); // Try to parse JSON error body
            console.error('Failed to send message:', response.status, errorData);
            // Append a system message displaying the error details from the backend
            appendMessage('system', `Error: ${response.status} - ${errorData.detail || JSON.stringify(errorData)}`);
            return; // Stop execution after error
        }

        // If message is sent successfully (e.g., 200 OK)
        const responseData = await response.json(); // Parse the JSON response body
        console.log('Successfully received response from query:', responseData);

        // Append the assistant's reply to the chat window
        // The responseData should contain 'answer' and optionally 'source_documents'
        appendMessage('assistant', responseData.answer, responseData.source_documents);

    } catch (error) {
        // This catch block handles network errors or other exceptions during the fetch
        console.error('Network or server error sending message:', error);
        // Append a generic system error message
        appendMessage('system', 'Error: Could not send message due to network or server connection issue.');
    } finally {
        // Always re-enable input fields after the attempt (success or failure)
        if (messageInput) messageInput.disabled = false;
        if (sendMessageBtn) sendMessageBtn.disabled = false;
        if (messageInput) messageInput.focus(); // Return focus to the input field for the next message
    }
}


// --- Document List and Selection ---

// Function to load available documents from the backend's /documents endpoint
async function loadAvailableDocuments() {
    console.log('Attempting to load available documents from:', `${backendApiUrl}/documents`);
    try {
        const response = await fetch(`${backendApiUrl}/documents`);
        if (!response.ok) {
            const errorData = await response.json().catch(() => ({ detail: response.statusText }));
            console.error('Failed to load documents:', response.status, errorData);
            // Optionally display an error message in the UI
            // appendMessage('system', `Error loading documents: ${response.status} - ${errorData.detail || JSON.stringify(errorData)}`);
            return;
        }

        const availableDocuments = await response.json();
        console.log('Successfully loaded available documents:', availableDocuments);

        // Clear the current document list and status messages in the UI
        if (documentsList) documentsList.innerHTML = '';
        if (documentStatusContainer) documentStatusContainer.innerHTML = ''; // Assuming this is for global status messages

        // Populate the UI list with available documents
        if (documentsList) { // Check if element was found
            availableDocuments.forEach(doc => {
                const docItem = document.createElement('li');
                docItem.classList.add('document-item');
                docItem.dataset.docId = doc.id; // Store document ID as a data attribute
                // Display filename and document type
                docItem.innerHTML = `<strong>${doc.filename}</strong> (${doc.document_type})`;

                // Add a visual status indicator element
                const statusSpan = document.createElement('span');
                statusSpan.classList.add('document-status-indicator', doc.status.toLowerCase()); // Add status class (e.g., 'completed', 'pending')
                statusSpan.textContent = doc.status; // Display status text (e.g., 'COMPLETED')

                // Add a tooltip for error messages if present
                if (doc.error_message) {
                    statusSpan.title = `Error: ${doc.error_message}`;
                } else {
                     statusSpan.title = ''; // Clear tooltip if no error
                }
                docItem.appendChild(statusSpan); // Add status indicator to the list item


                // Add click listener for selection (or a checkbox could be used)
                // Only make the item interactive if it's 'COMPLETED' or 'PROCESSABLE' for RAG
                if (doc.status === 'COMPLETED') {
                    docItem.classList.add('processable'); // Add a class indicating it's ready for processing/selection
                     docItem.classList.remove('non-processable');
                     // Add click handler for selection toggle
                     docItem.addEventListener('click', () => toggleDocumentSelection(doc.id, docItem));
                } else {
                     // Indicate non-processable status visually
                     docItem.classList.add('non-processable');
                     // Optional: Add a tooltip explaining why it's not processable
                     if (!doc.error_message) { // If no specific error, provide a generic status reason
                         statusSpan.title = `Document status: ${doc.status}. Cannot be selected for chat grounding until COMPLETED.`;
                     }
                }


                documentsList.appendChild(docItem); // Add the document item to the list
            });
        } else {
             console.error("documentsList element not found.");
        }


        // After loading, update the UI based on the current session's selectedDocumentIds
        updateDocumentSelectionUI();

        // After documents are loaded, initiate WebSocket connections for documents
        // that need ongoing status tracking (pending, processing, downloading)
        // The connectToDocumentStatuses function is called with the list of loaded documents
        // It will internally filter and connect for the relevant ones
        // This call is now placed after loadAvailableDocuments
        connectToDocumentStatuses(availableDocuments);


    } catch (error) {
        console.error('Network or server error loading documents:', error);
        // appendMessage('system', 'Error: Could not load available documents due to network or server connection issue.');
    }
}

// Function to toggle document selection in the UI and update state
function toggleDocumentSelection(docId, docElement) {
    const id = parseInt(docId); // Ensure ID is an integer

    // Prevent selecting/unselecting non-processable documents
    if (docElement && !docElement.classList.contains('processable')) { // Check if docElement exists and is processable
        console.warn(`Attempted to select non-processable document ID: ${id}. Status: ${docElement.querySelector('.document-status-indicator')?.textContent}`);
        // Optionally provide user feedback (e.g., a subtle visual indication)
        return; // Do not proceed with selection
    }


    const index = selectedDocumentIds.indexOf(id); // Check if the ID is already in the selected array

    if (index > -1) {
        // Document is currently selected, remove it from the selected IDs array
        selectedDocumentIds.splice(index, 1);
        if (docElement) docElement.classList.remove('selected'); // Remove the 'selected' class from the UI element if element exists
        console.log(`Unselected document ID: ${id}`);
    } else {
        // Document is not selected, add it to the selected IDs array
        selectedDocumentIds.push(id);
        if (docElement) docElement.classList.add('selected'); // Add the 'selected' class to the UI element if element exists
         console.log(`Selected document ID: ${id}`);
    }
     console.log("Current selected document IDs for grounding:", selectedDocumentIds);
    // Note: This UI selection primarily affects which documents are used for the *next* query sent.
    // It does NOT automatically link/unlink documents to the chat session in the backend.
    // Linking/unlinking documents to a session would require separate API calls.
}

// Function to update the visual state of the document list based on selectedDocumentIds state
function updateDocumentSelectionUI() {
     // Remove the 'selected' class from all document list items first
     if (documentsList) { // Check if element was found
         documentsList.querySelectorAll('.document-item').forEach(item => {
             item.classList.remove('selected');
         });
     } else {
         console.error("documentsList element not found during selection UI update.");
         return; // Cannot update UI if list is not found
     }


     // Iterate through the list of selected document IDs
     selectedDocumentIds.forEach(docId => {
         // Find the corresponding document list item using its data-doc-id attribute
         const docItem = documentsList.querySelector(`.document-item[data-doc-id="${docId}"]`);
         if (docItem) {
             // If the document item exists, add the 'selected' class
             docItem.classList.add('selected');
         }
     });
      console.log("UI updated based on selected document IDs:", selectedDocumentIds);
}


// Function to connect to WebSocket for document status updates
// Revised to connect for documents that are not yet completed
function connectToDocumentStatuses(documents) {
    // Filter documents that are still pending, downloading, or processing
    const docsToTrack = documents.filter(doc =>
        doc.status !== 'COMPLETED' && doc.status !== 'FAILED'
    );

    console.log(`Attempting to connect to WebSocket for status updates for ${docsToTrack.length} documents.`);

    docsToTrack.forEach(doc => {
        // Ensure window.BACKEND_API_URL is correctly set (e.g., http://192.168.2.211:8000)
        // Need to convert http(s) to ws(s) for WebSocket connection
        const wsUrl = backendApiUrl.replace(/^http/, 'ws') + `/ws/status/${doc.id}`;
        console.log(`Connecting to WebSocket for document ${doc.id} at: ${wsUrl}`);

        try {
            const websocket = new WebSocket(wsUrl);

            websocket.onopen = (event) => {
                console.log(`WebSocket connection opened for doc ${doc.id}:`, event);
                // You could send a message to subscribe to certain updates if needed
            };

            websocket.onmessage = (event) => {
                const statusData = JSON.parse(event.data);
                console.log(`WebSocket message received for doc ${doc.id}:`, statusData);
                // Update UI for the specific document status
                updateDocumentStatusUI(statusData.doc_id, statusData.status, statusData.error_message);
                // If status is COMPLETED or FAILED, close this specific websocket connection
                if (statusData.status === 'COMPLETED' || statusData.status === 'FAILED') {
                    console.log(`Closing WebSocket for doc ${doc.id} due to final status.`);
                    websocket.close();
                }
            };

            websocket.onerror = (event) => {
                console.error(`WebSocket error for doc ${doc.id}:`, event);
                // Update UI to show an error state for the document status
                 updateDocumentStatusUI(doc.id, 'FAILED', 'WebSocket Error'); // Indicate WS error
            };

            websocket.onclose = (event) => {
                console.log(`WebSocket closed for doc ${doc.id}:`, event);
                // Attempt to reconnect if closed unexpectedly and status isn't final
                if (!event.wasClean && doc.status !== 'COMPLETED' && doc.status !== 'FAILED') {
                     console.warn(`WebSocket connection for doc ${doc.id} died unexpectedly. Attempting to reconnect...`);
                     // Implement a reconnection strategy (e.g., exponential backoff)
                     // Be careful with rapid reconnections if the server is down
                     setTimeout(() => connectToDocumentStatuses([doc]), 5000); // Retry connection after 5 seconds
                }
            };
        } catch (error) {
            console.error(`Error connecting to WebSocket for doc ${doc.id}:`, error);
             updateDocumentStatusUI(doc.id, 'FAILED', 'WebSocket Connection Error'); // Indicate connection error
        }
    });
}


// Function to update UI for individual document status based on WebSocket messages or polling
// This function is called by the WebSocket message handler or potentially polling logic
function updateDocumentStatusUI(docId, status, errorMessage) {
     console.log(`Updating UI for document ${docId}: Status - ${status}, Error - ${errorMessage}`);
     // Find the document list item using its data-doc-id attribute
     const docItem = document.querySelector(`.document-item[data-doc-id="${docId}"]`);
     if (docItem) {
         // Find the status indicator element within the list item
         const statusSpan = docItem.querySelector('.document-status-indicator');
         if (statusSpan) {
             // Remove all existing status classes (pending, downloading, etc.)
             statusSpan.classList.remove('pending', 'downloading', 'processing', 'completed', 'failed');
             // Add the new status class (converted to lowercase)
             statusSpan.classList.add(status.toLowerCase());
             // Update the displayed text content of the status
             statusSpan.textContent = status;
             // Update the tooltip text for the status
             if (errorMessage) {
                 statusSpan.title = `Error: ${errorMessage}`;
             } else {
                 statusSpan.title = ''; // Clear tooltip if no error message
             }
         }
         // Update selectable status based on completion
         if (status === 'COMPLETED') {
             docItem.classList.add('processable'); // Add a class indicating it's ready for processing/selection
             docItem.classList.remove('non-processable');
             // Re-add the click listener if it was removed or wasn't added initially
             // Ensure event listener is not duplicated if already added
             // Check if listener is already added using a data attribute
              let listenerAdded = docItem.dataset.listenerAdded === 'true';
              if (!listenerAdded) {
                  // Add click listener for selection toggle
                  docItem.addEventListener('click', () => toggleDocumentSelection(docId, docItem)); // Use docId parameter
                  docItem.dataset.listenerAdded = 'true'; // Mark as added
              }
         } else {
              docItem.classList.remove('processable');
              docItem.classList.add('non-processable');
              // Optional: Remove click listener if it's not selectable
              // Need to store the handler function to remove it properly
              let listenerAdded = docItem.dataset.listenerAdded === 'true';
              if (listenerAdded) {
                   // This requires storing the actual handler function reference to remove it
                   // For simplicity, we might rely on the processable check inside toggleDocumentSelection
                   // or just leave the listener and have toggleDocumentSelection check the class.
                   // Let's rely on the check inside toggleDocumentSelection for now.
              }
         }
     }
     // After updating a document status, re-evaluate the selected documents for the *current* session
     // This is important if a document linked to the session just completed processing
     if (currentChatSessionId !== null) {
          // Reload the session documents to update the selectedDocumentIds state
          // This ensures that if a document completes, and is linked to the current session,
          // its status in the document list and potential selectability is updated,
          // and the selectedDocumentIds array for the current session is correct.
          // This might be slightly heavy if many docs update, consider optimizing if needed.
          loadSessionDocuments(currentChatSessionId);
     }
}


// Function to get the IDs of currently selected documents from the UI list
function getSelectedDocumentIds() {
    const selectedIds = [];
    // Find all document items that have the 'selected' class
    // Ensure documentsList element exists before querying
    if (documentsList) {
        documentsList.querySelectorAll('.document-item.selected').forEach(item => {
            const docId = item.dataset.docId; // Get the document ID from the data attribute
            if (docId) {
                selectedIds.push(parseInt(docId)); // Convert to integer and add to the array
            }
        });
    } else {
        console.error("documentsList element not found when getting selected IDs.");
    }
    console.log("Retrieved selected document IDs from UI:", selectedIds);
    return selectedIds; // Return the array of selected document IDs
}


// --- Event Listeners ---

// Define event listeners within the DOMContentLoaded block
document.addEventListener('DOMContentLoaded', async () => {
    console.log('DOM fully loaded. Initializing application...');

    // Get references to DOM elements now that the DOM is ready
    chatSessionsList = document.getElementById('chat-sessions-list');
    chatWindow = document.getElementById('chat-window');
    messagesContainer = document.getElementById('messages-container');
    messageInput = document.getElementById('message-input');
    sendMessageBtn = document.getElementById('send-message-btn');
    newChatBtn = document.getElementById('new-chat-btn');
    documentListContainer = document.getElementById('document-list-container');
    documentsList = document.getElementById('documents-list');
    documentStatusContainer = document.getElementById('document-status-container');

    // Add checks to ensure elements were found
    if (!chatSessionsList) console.error("Element with ID 'chat-sessions-list' not found.");
    if (!chatWindow) console.error("Element with ID 'chat-window' not found.");
    if (!messagesContainer) console.error("Element with ID 'messages-container' not found.");
    if (!messageInput) console.error("Element with ID 'message-input' not found.");
    if (!sendMessageBtn) console.error("Element with ID 'send-message-btn' not found.");
    if (!newChatBtn) console.error("Element with ID 'new-chat-btn' not found.");
    if (!documentListContainer) console.error("Element with ID 'document-list-container' not found.");
    if (!documentsList) console.error("Element with ID 'documents-list' not found.");
    if (!documentStatusContainer) console.error("Element with ID 'document-status-container' not found.");


    // Add event listeners now that the elements are referenced
    // Check if elements were found before adding listeners
    if (sendMessageBtn) sendMessageBtn.addEventListener('click', sendChatMessage);
    else console.error("sendMessageBtn not found, cannot add event listener.");

    if (messageInput) {
        messageInput.addEventListener('keypress', (event) => {
            if (event.key === 'Enter') {
                event.preventDefault();
                sendChatMessage();
            }
        });
    } else console.error("messageInput not found, cannot add keypress listener.");


    if (newChatBtn) newChatBtn.addEventListener('click', createNewChatSession);
    else console.error("newChatBtn not found, cannot add event listener.");


    // Load existing chat sessions from the backend
    await loadChatSessions();
    // Load the list of available documents from the backend
    await loadAvailableDocuments();

    // WebSocket connections for documents that need status tracking are initiated
    // inside loadAvailableDocuments now, after the documents are loaded.


    console.log('Application initialization complete.');
});
