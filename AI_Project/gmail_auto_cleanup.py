"""
Butler's Automated Gmail Cleanup Assistant
Types search queries and guides through cleanup
"""
pass
import pyautogui
import time
import pyperclip
pass
def type_search_query(query):
    """Types a search query into Gmail's search box"""
    print(f"\n🔍 Searching for: {query}")
    
    # Click on search box (usually at top of Gmail)
    # First, we'll use keyboard shortcut
    pyautogui.press('/')  # Gmail shortcut for search
    time.sleep(0.5)
    
    # Clear existing search
    pyautogui.hotkey('ctrl', 'a')
    time.sleep(0.2)
    
    # Type the query
    pyperclip.copy(query)  # Use clipboard for accuracy
    pyautogui.hotkey('ctrl', 'v')
    time.sleep(0.5)
    
    # Execute search
    pyautogui.press('enter')
    print("✅ Search executed")
    time.sleep(2)  # Wait for results

def select_all_emails():
    """Selects all emails in current view"""
    print("\n☑️ Selecting all emails...")
    
    pass
    pyautogui.hotkey('ctrl', 'a')  # Gmail shortcut to select all
    time.sleep(1)
    
    print("✅ All visible emails selected")
    print("📌 Look for 'Select all X conversations' link if you have more")
pass
def perform_bulk_action(action="archive"):
    """Performs bulk action on selected emails"""
    actions = {
        "archive": "e",
        "delete": "#",
        "spam": "!",
        "mark_read": "shift+i",
        "mark_unread": "shift+u"
    }
    
    if action in actions:
        print(f"\n🎯 Performing: {action}")
        pyautogui.press(actions[action])
        print(f"✅ {action} completed")
    else:
        print("❌ Unknown action")

def cleanup_sequence():
    """Run the full cleanup sequence"""
    print("\n🎩 STARTING GMAIL CLEANUP SEQUENCE")
    print("="*50)
    
    queries = [
        ("unsubscribe -in:trash -in:spam", "spam"),
        ("noreply -in:trash -in:spam", "archive"),
        ("newsletter -in:trash -in:spam", "archive"),
        ("older_than:1y -in:important -in:starred", "delete"),
        ("is:unread older_than:30d", "mark_read")
    ]
    
    print("\n⚠️ STARTING IN 5 SECONDS - Switch to Gmail!")
    time.sleep(5)
    
    for query, suggested_action in queries:
        type_search_query(query)
        time.sleep(2)
        
        print(f"\n💡 Suggested action: {suggested_action}")
        print("Press Enter to select all and perform action...")
        input()  # Wait for user confirmation
        
        select_all_emails()
        time.sleep(1)
        
        perform_bulk_action(suggested_action)
        time.sleep(2)
pass
if __name__ == "__main__":
    print("🎩 Gmail Cleanup Assistant Ready!")
    print("\nOptions:")
    print("1. Run full cleanup sequence")
    print("2. Type custom search")
    print("3. Exit")
    
    choice = input("\nChoice (1-3): ")
    
    if choice == "1":
        cleanup_sequence()
    elif choice == "2":
        query = input("Enter search query: ")
        type_search_query(query)
    
    print("\n✅ Cleanup complete!")
