#include <iostream>
#include <thread>
#include <atomic>
#include <boost/asio.hpp>
#include <portaudio.h>

using boost::asio::ip::tcp;

constexpr int SAMPLE_RATE = 44100;
constexpr int FRAMES_PER_BUFFER = 512;
constexpr int CHANNELS = 1;
constexpr int BUFFER_SIZE = FRAMES_PER_BUFFER * CHANNELS * sizeof(short);

std::atomic<bool> running{true};

// Audio capture callback (for client)
static int recordCallback(const void* inputBuffer, void* outputBuffer,
                          unsigned long framesPerBuffer,
                          const PaStreamCallbackTimeInfo* timeInfo,
                          PaStreamCallbackFlags statusFlags,
                          void* userData)
{
    tcp::socket* socket = reinterpret_cast<tcp::socket*>(userData);
    const char* data = reinterpret_cast<const char*>(inputBuffer);
    size_t bytes = framesPerBuffer * CHANNELS * sizeof(short);

    boost::system::error_code ec;
    boost::asio::write(*socket, boost::asio::buffer(data, bytes), ec);
    if (ec) {
        std::cerr << "Socket write error: " << ec.message() << std::endl;
        return paComplete;
    }

    return paContinue;
}

// Audio playback thread (for server)
void audioPlaybackThread(tcp::socket socket)
{
    PaStream* stream;
    Pa_Initialize();

    PaStreamParameters outputParameters;
    outputParameters.device = Pa_GetDefaultOutputDevice();
    outputParameters.channelCount = CHANNELS;
    outputParameters.sampleFormat = paInt16;
    outputParameters.suggestedLatency = Pa_GetDeviceInfo(outputParameters.device)->defaultLowOutputLatency;
    outputParameters.hostApiSpecificStreamInfo = nullptr;

    Pa_OpenStream(&stream, nullptr, &outputParameters, SAMPLE_RATE, FRAMES_PER_BUFFER, paNoFlag, nullptr, nullptr);
    Pa_StartStream(stream);

    std::vector<char> buffer(BUFFER_SIZE);
    boost::system::error_code ec;

    while (running)
    {
        size_t len = socket.read_some(boost::asio::buffer(buffer), ec);
        if (ec == boost::asio::error::eof || ec) {
            std::cerr << "Connection closed or error: " << ec.message() << std::endl;
            break;
        }
        Pa_WriteStream(stream, buffer.data(), FRAMES_PER_BUFFER);
    }

    Pa_StopStream(stream);
    Pa_CloseStream(stream);
    Pa_Terminate();
}

// Run client
void runClient(const std::string& server_ip, int port)
{
    boost::asio::io_context io_context;
    tcp::socket socket(io_context);
    socket.connect(tcp::endpoint(boost::asio::ip::address::from_string(server_ip), port));

    Pa_Initialize();

    PaStreamParameters inputParameters;
    inputParameters.device = Pa_GetDefaultInputDevice();
    if (inputParameters.device == paNoDevice) {
        std::cerr << "No default input device.\n";
        return;
    }

    inputParameters.channelCount = CHANNELS;
    inputParameters.sampleFormat = paInt16;
    inputParameters.suggestedLatency = Pa_GetDeviceInfo(inputParameters.device)->defaultLowInputLatency;
    inputParameters.hostApiSpecificStreamInfo = nullptr;

    PaStream* stream;
    Pa_OpenStream(&stream, &inputParameters, nullptr, SAMPLE_RATE, FRAMES_PER_BUFFER, paNoFlag, recordCallback, &socket);
    Pa_StartStream(stream);

    std::cout << "Streaming audio to server...\nPress Enter to stop." << std::endl;
    std::cin.get();

    running = false;
    Pa_StopStream(stream);
    Pa_CloseStream(stream);
    Pa_Terminate();
    socket.close();
}

// Run server
void runServer(int port)
{
    boost::asio::io_context io_context;
    tcp::acceptor acceptor(io_context, tcp::endpoint(tcp::v4(), port));

    std::cout << "Waiting for client to connect..." << std::endl;
    tcp::socket socket(io_context);
    acceptor.accept(socket);

    std::cout << "Client connected, playing audio..." << std::endl;

    std::thread playbackThread(audioPlaybackThread, std::move(socket));
    playbackThread.join();
}

int main(int argc, char* argv[])
{
    if (argc < 2) {
        std::cout << "Usage: audio_streamer <client/server> [server_ip]\n";
        return 1;
    }

    std::string role = argv[1];
    if (role == "client") {
        if (argc < 3) {
            std::cerr << "Client mode requires server IP address.\n";
            return 1;
        }
        runClient(argv[2], 50007);
    }
    else if (role == "server") {
        runServer(50007);
    }
    else {
        std::cerr << "Unknown role. Use 'client' or 'server'.\n";
        return 1;
    }

    return 0;
}
