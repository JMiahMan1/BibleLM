<?php
require_once 'includes/api_client.php';

// --- Fetch Initial Data from Backend ---
// Adjust endpoints based on your actual API structure
$sources = fetchDataFromApi('/api/sources/') ?? []; // Assuming GET /api/sources/ lists sources
$chats = fetchDataFromApi('/api/chats/') ?? []; // Assuming GET /api/chats/ lists available chats
$initialChatData = null;
$initialMessages = [];
$currentChatId = null;

// Let's try to load the first chat by default, or handle case with no chats
if (!empty($chats)) {
    $currentChatId = $chats[0]['id'] ?? null; // Assuming chat objects have an 'id'
    if ($currentChatId) {
        // Fetch details for the first chat
        $initialChatData = fetchDataFromApi("/api/chats/{$currentChatId}");
        // Fetch messages for the first chat
        $initialMessages = fetchDataFromApi("/api/chats/{$currentChatId}/messages/") ?? [];
    }
}

// Placeholder for Studio data - Define an endpoint in your backend for this
// e.g., GET /api/studio/overview
$studioOverview = fetchDataFromApi('/api/studio/overview') ?? [
    'title' => 'Studio',
    'items' => [],
    'notes_placeholder' => 'Notes unavailable.',
    'quick_links' => []
];

// Determine Page Title (use chat title if available)
$pageTitle = $initialChatData['title'] ?? 'BibleLM Interface'; // Assuming chat data has a 'title'

?>
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title><?php echo htmlspecialchars($pageTitle); ?></title>
    <link rel="stylesheet" href="style.css">
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
    </head>
<body>
    <div class="app-container">
        <header class="app-header">
            <div class="header-title">
                <h1><?php echo htmlspecialchars($pageTitle); ?></h1>
            </div>
            <div class="header-actions">
                <button class="icon-button" aria-label="Sync" title="Sync">
                    <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12a9 9 0 0 0-9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"/><path d="M3 12a9 9 0 0 0 9 9 9.75 9.75 0 0 0 6.74-2.74L21 16"/><path d="M3 8v4h4"/><path d="M21 16v-4h-4"/></svg>
                </button>
                <button class="icon-button" aria-label="Settings" title="Settings">
                     <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"/></svg>
                </button>
                <img src="assets/placeholder-icon.svg" alt="User Avatar" class="avatar">
            </div>
        </header>

        <div class="main-container" data-current-chat-id="<?php echo htmlspecialchars($currentChatId ?? ''); ?>">
            <aside class="sidebar sidebar-left">
                <div class="sidebar-header">
                    <h2>Sources</h2>
                    <div class="sidebar-actions">
                        <button class="button button-small button-secondary">+ Add</button>
                        <button class="button button-small button-secondary">🔍 Discover</button>
                    </div>
                </div>
                <div class="source-controls">
                    <label class="checkbox-label">
                        <input type="checkbox" id="select-all-sources">
                        <span>Select all sources</span>
                    </label>
                </div>
                <ul class="source-list scrollable" id="source-list">
                    <?php if (!empty($sources)): ?>
                        <?php foreach ($sources as $source): ?>
                            <li data-source-id="<?php echo htmlspecialchars($source['id']); ?>" tabindex="0">
                                <img src="assets/placeholder-icon.svg" alt="" class="source-icon">
                                <span class="source-title"><?php echo htmlspecialchars($source['title'] ?? 'Untitled Source'); ?></span>
                                <input type="checkbox" class="source-checkbox" aria-label="Select <?php echo htmlspecialchars($source['title'] ?? 'Untitled Source'); ?>">
                            </li>
                        <?php endforeach; ?>
                    <?php else: ?>
                        <li class="empty-list-message">No sources found.</li>
                    <?php endif; ?>
                </ul>
            </aside>

            <main class="content-center" id="main-content">
                <?php if ($initialChatData): ?>
                    <div class="chat-header">
                        <img src="assets/placeholder-icon.svg" alt="" class="chat-topic-icon">
                        <h2 id="chat-title"><?php echo htmlspecialchars($initialChatData['title'] ?? 'Chat'); ?></h2>
                        </div>
                    <div class="chat-body scrollable" id="chat-body">
                        <?php foreach ($initialMessages as $message): ?>
                            <div class="chat-message <?php echo ($message['role'] ?? 'user') === 'assistant' ? 'assistant-message' : 'user-message'; ?>">
                                <p><?php echo nl2br(htmlspecialchars($message['content'] ?? '')); ?></p>
                                </div>
                        <?php endforeach; ?>
                         <?php if (empty($initialMessages)): ?>
                             <p class="empty-list-message">Start the conversation!</p>
                         <?php endif; ?>
                    </div>
                    <div class="chat-actions" id="chat-actions">
                        <button class="button button-outline">Add note</button>
                        <button class="button button-outline">Audio Overview</button>
                        <button class="button button-outline">Mind Map</button>
                        <button class="button icon-button" aria-label="Save to note" title="Save to note">
                           <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z"/><polyline points="17 21 17 13 7 13 7 21"/><polyline points="7 3 7 8 15 8"/></svg>
                        </button>
                    </div>
                    <div class="chat-input-area">
                        <textarea id="chat-input" placeholder="Start typing..." aria-label="Chat input" rows="1"></textarea>
                        <button class="button button-primary icon-button" id="send-button" aria-label="Send message" title="Send message">
                            <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/></svg>
                        </button>
                    </div>
                <?php else: ?>
                    <div class="centered-message">
                        <h2>Welcome!</h2>
                        <p>Select a chat or create a new one to get started.</p>
                        <button class="button button-primary" id="create-chat-button">Create New Chat</button>
                    </div>
                <?php endif; ?>
            </main>

            <aside class="sidebar sidebar-right">
                <div class="sidebar-header">
                    <h2><?php echo htmlspecialchars($studioOverview['title'] ?? 'Studio'); ?></h2>
                     <button class="icon-button" aria-label="Help" title="Help">
                        <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>
                     </button>
                </div>
                <div class="studio-content scrollable">
                    <div class="studio-section">
                        <h3>Audio Overview</h3> <?php if (!empty($studioOverview['items'])): ?>
                             <?php foreach($studioOverview['items'] as $item): ?>
                             <div class="studio-item" data-item-id="<?php echo htmlspecialchars($item['id'] ?? ''); ?>">
                                 <h4><?php echo htmlspecialchars($item['title'] ?? 'Item'); ?></h4>
                                 <p><?php echo htmlspecialchars($item['details'] ?? ''); ?></p>
                                 <div class="studio-item-actions">
                                     <button class="button button-outline button-small">Customize</button>
                                     <button class="button button-primary button-small">Generate</button>
                                 </div>
                             </div>
                             <?php endforeach; ?>
                        <?php else: ?>
                             <p class="placeholder">No studio items available.</p>
                        <?php endif; ?>
                    </div>
                    <div class="studio-section">
                        <div class="section-header">
                             <h3>Notes</h3>
                             <button class="button button-small button-secondary">+ Add Note</button>
                        </div>
                         <div class="notes-area" id="notes-area">
                             <p class="placeholder"><?php echo htmlspecialchars($studioOverview['notes_placeholder'] ?? 'Saved notes will appear here.'); ?></p>
                         </div>
                    </div>
                    <div class="studio-section quick-links">
                         <h3>Tools</h3>
                         <?php if (!empty($studioOverview['quick_links'])): ?>
                             <?php foreach($studioOverview['quick_links'] as $link): ?>
                                <button class="button button-link"><?php echo htmlspecialchars($link); ?></button>
                             <?php endforeach; ?>
                         <?php else: ?>
                              <p class="placeholder">No tools configured.</p>
                         <?php endif; ?>
                    </div>
                </div>
            </aside>
        </div>
    </div>

    <script src="js/main.js"></script>
</body>
</html>
