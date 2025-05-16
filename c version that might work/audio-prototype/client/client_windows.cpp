#include <iostream>
#include <portaudio.h>
#include <winsock2.h>

#define SAMPLE_RATE 44100
#define FRAMES_PER_BUFFER 4096
#define PORT 50007

int main() {
    const char* server_ip = getenv("SERVER_IP");
    if (!server_ip) server_ip = "127.0.0.1";

    // Setup Winsock
    WSADATA wsa;
    WSAStartup(MAKEWORD(2,2), &wsa);

    SOCKET sock = socket(AF_INET, SOCK_STREAM, 0);
    sockaddr_in server {};
    server.sin_family = AF_INET;
    server.sin_port = htons(PORT);
    server.sin_addr.s_addr = inet_addr(server_ip);

    connect(sock, (sockaddr*)&server, sizeof(server));
    std::cout << "Connected to server.\n";

    // Init PortAudio
    Pa_Initialize();
    PaStream* stream;
    Pa_OpenDefaultStream(&stream, 1, 0, paInt16, SAMPLE_RATE, FRAMES_PER_BUFFER, nullptr, nullptr);
    Pa_StartStream(stream);

    int16_t buffer[FRAMES_PER_BUFFER];
    while (true) {
        Pa_ReadStream(stream, buffer, FRAMES_PER_BUFFER);
        send(sock, (char*)buffer, sizeof(buffer), 0);
    }

    Pa_StopStream(stream);
    Pa_CloseStream(stream);
    Pa_Terminate();
    closesocket(sock);
    WSACleanup();
    return 0;
}
