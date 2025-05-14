// Compile with: cl audio_client.cpp /link Ole32.lib Ws2_32.lib
#include <audioclient.h>
#include <mmdeviceapi.h>
#include <winsock2.h>
#include <ws2tcpip.h>
#include <iostream>

#define SERVER_IP "192.168.1.100"  // Replace with your Linux server IP
#define SERVER_PORT 5000
#define BUF_SIZE 4800  // 100 frames of 48kHz 16-bit stereo

int main() {
    // Initialize Winsock
    WSADATA wsa;
    WSAStartup(MAKEWORD(2,2), &wsa);

    // Connect to server
    SOCKET sock = socket(AF_INET, SOCK_STREAM, 0);
    sockaddr_in serv{};
    serv.sin_family = AF_INET;
    serv.sin_port = htons(SERVER_PORT);
    inet_pton(AF_INET, SERVER_IP, &serv.sin_addr);

    if (connect(sock, (sockaddr*)&serv, sizeof(serv)) != 0) {
        std::cerr << "Connection failed\n";
        return 1;
    }
    std::cout << "Connected to server\n";

    // WASAPI setup
    CoInitialize(nullptr);
    IMMDeviceEnumerator* pEnum = nullptr;
    IMMDevice* pDevice = nullptr;
    IAudioClient* pAudioClient = nullptr;
    IAudioCaptureClient* pCaptureClient = nullptr;

    CoCreateInstance(__uuidof(MMDeviceEnumerator), nullptr, CLSCTX_ALL, IID_PPV_ARGS(&pEnum));
    pEnum->GetDefaultAudioEndpoint(eRender, eConsole, &pDevice);

    pDevice->Activate(__uuidof(IAudioClient), CLSCTX_ALL, nullptr, (void**)&pAudioClient);

    WAVEFORMATEX* pwfx = nullptr;
    pAudioClient->GetMixFormat(&pwfx);
    pAudioClient->Initialize(AUDCLNT_SHAREMODE_SHARED,
                             AUDCLNT_STREAMFLAGS_LOOPBACK,
                             10000000, 0, pwfx, nullptr);

    pAudioClient->Start();
    pAudioClient->GetService(IID_PPV_ARGS(&pCaptureClient));

    BYTE* pData;
    UINT32 packetLength = 0;
    DWORD flags;
    while (true) {
        pCaptureClient->GetNextPacketSize(&packetLength);
        if (packetLength == 0) {
            Sleep(10);
            continue;
        }

        UINT32 numFrames;
        pCaptureClient->GetBuffer(&pData, &numFrames, &flags, nullptr, nullptr);
        int bytes = numFrames * pwfx->nBlockAlign;
        send(sock, (const char*)pData, bytes, 0);
        pCaptureClient->ReleaseBuffer(numFrames);
    }

    closesocket(sock);
    CoUninitialize();
    return 0;
}
