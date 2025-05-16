#include <iostream>
#include <cstdlib>
#include <string>

#ifdef _WIN32
#define PYTHON "client_windows.exe"
#else
#define PYTHON "./client_linux"
#endif

int main() {
    std::string mode, ip;
    std::cout << "Run as (client/server): ";
    std::cin >> mode;

    if (mode == "client") {
        std::cout << "Enter server IP: ";
        std::cin >> ip;
        setenv("SERVER_IP", ip.c_str(), 1);
        std::system(("client/" PYTHON).c_str());
    } else if (mode == "server") {
        std::system("server/server_linux"); // or server_windows
    } else {
        std::cerr << "Invalid mode.\n";
    }

    return 0;
}
