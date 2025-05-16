#include <X11/Xlib.h>
#include <X11/extensions/XTest.h>
#include "mouse.h"

void move_mouse_by(int dx, int dy) {
    Display *dpy = XOpenDisplay(NULL);
    if (dpy == NULL) return;
    XTestFakeRelativeMotionEvent(dpy, dx, dy, CurrentTime);
    XFlush(dpy);
    XCloseDisplay(dpy);
}
