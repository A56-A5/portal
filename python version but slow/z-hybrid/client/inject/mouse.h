#ifndef MOUSE_H
#define MOUSE_H

#ifdef _WIN32
__declspec(dllexport)
#else
__attribute__((visibility("default")))
#endif
void move_mouse_by(int dx, int dy);

#endif
