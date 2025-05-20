#include <windows.h>
#include <iostream>

// Global variables
HHOOK hMouseHook = NULL;
POINT originalPos;

// Low-level mouse hook procedure
LRESULT CALLBACK LowLevelMouseProc(int nCode, WPARAM wParam, LPARAM lParam) {
    if (nCode == HC_ACTION && wParam == WM_MOUSEMOVE) {
        MSLLHOOKSTRUCT* pMouseStruct = (MSLLHOOKSTRUCT*)lParam;
        if (pMouseStruct != NULL) {
            // Print mouse position
            std::cout << "Mouse moved to: " << pMouseStruct->pt.x << ", " << pMouseStruct->pt.y << std::endl;

            // Reset cursor position to original
            SetCursorPos(originalPos.x, originalPos.y);

            // Block the event by returning a non-zero value
            return 1;
        }
    }
    // Call next hook if not handled
    return CallNextHookEx(hMouseHook, nCode, wParam, lParam);
}

int main() {
    // Get initial cursor position to lock it there
    GetCursorPos(&originalPos);

    // Install the low-level mouse hook
    hMouseHook = SetWindowsHookEx(WH_MOUSE_LL, LowLevelMouseProc, NULL, 0);
    if (hMouseHook == NULL) {
        std::cerr << "Failed to install mouse hook!" << std::endl;
        return 1;
    }
    std::cout << "Mouse hook installed. Press Ctrl+C to exit." << std::endl;

    // Message loop to keep the hook alive
    MSG msg;
    while (GetMessage(&msg, NULL, 0, 0)) {
        TranslateMessage(&msg);
        DispatchMessage(&msg);
    }

    // Unhook before exit
    UnhookWindowsHookEx(hMouseHook);
    return 0;
}
