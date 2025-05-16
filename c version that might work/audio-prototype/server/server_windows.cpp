#include <iostream>
#include <portaudio.h>
#include <winsock2.h>

#define SAMPLE_RATE 44100
#define FRAMES_PER_BUFFER 1024
#define PORT 50007

int main() {
    WSADATA wsa;
    WSAStartup(MAKEWORD(2,2), &wsa);

    SOCKET server = socket(AF_INET, SOCK_STREAM, 0);
    sockaddr_in addr {};
    addr.sin_family = AF_INET;
    addr.sin_addr.s_addr = INADDR_ANY;
    addr.sin_port = htons(PORT);

    bind(server, (sockaddr*)&addr, sizeof(addr));
    listen(server, 1);

    std::cout << "Waiting for connection...\n";
    SOCKET client = accept(server, nullptr, nullptr);
    std::cout << "Client connected.\n";

    Pa_Initialize();
    PaStream* stream;
    Pa_OpenDefaultStream(&stream, 0, 1, paInt16, SAMPLE_RATE, FRAMES_PER_BUFFER, nullptr, nullptr);
    Pa_StartStream(stream);

    int16_t buffer[FRAMES_PER_BUFFER];
    while (true) {
        int bytes = recv(client, (char*)buffer, sizeof(buffer), 0);
        if (bytes <= 0) break;
        Pa_WriteStream(stream, buffer, bytes / sizeof(int16_t));
    }

    Pa_StopStream(stream);
    Pa_CloseStream(stream);
    Pa_Terminate();
    closesocket(client);
    closesocket(server);
    WSACleanup();
    return 0;
}
