/*
 * Minimal PCM I/O backend for the THAW P8 port's MinGW build (no libsndfile, no MSVC):
 * reads 16-bit PCM RIFF/WAVE files only (what ffmpeg writes for the encoder). LGPL-2.1, as AtracDEnc.
 */

#include "wav.h"

#include <cstdint>
#include <cstdio>
#include <cstring>
#include <stdexcept>
#include <vector>

class TPCMIORawWav : public IPCMProviderImpl {
public:
    explicit TPCMIORawWav(const std::string& filename) {
        F = std::fopen(filename.c_str(), "rb");
        if (!F)
            throw std::runtime_error("unable to open input file '" + filename + "'");
        char riff[12];
        if (std::fread(riff, 1, 12, F) != 12 || std::memcmp(riff, "RIFF", 4) || std::memcmp(riff + 8, "WAVE", 4))
            throw std::runtime_error("not a RIFF/WAVE file");
        bool fmt = false;
        for (;;) {
            char id[4];
            uint32_t len;
            if (std::fread(id, 1, 4, F) != 4 || std::fread(&len, 4, 1, F) != 1)
                throw std::runtime_error("no data chunk");
            if (!std::memcmp(id, "fmt ", 4)) {
                std::vector<uint8_t> b(len);
                if (std::fread(b.data(), 1, len, F) != len)
                    throw std::runtime_error("short fmt chunk");
                uint16_t tag, ch, bits;
                uint32_t rate;
                std::memcpy(&tag, &b[0], 2);
                std::memcpy(&ch, &b[2], 2);
                std::memcpy(&rate, &b[4], 4);
                std::memcpy(&bits, &b[14], 2);
                if ((tag != 1 && tag != 0xFFFE) || bits != 16)
                    throw std::runtime_error("only 16-bit PCM WAV input is supported");
                Channels = ch;
                Rate = rate;
                fmt = true;
                if (len & 1)
                    std::fseek(F, 1, SEEK_CUR);
            } else if (!std::memcmp(id, "data", 4)) {
                if (!fmt)
                    throw std::runtime_error("data before fmt");
                Total = len / (2 * Channels);
                break;
            } else {
                std::fseek(F, len + (len & 1), SEEK_CUR);
            }
        }
    }
    ~TPCMIORawWav() override {
        if (F)
            std::fclose(F);
    }
    size_t GetChannelsNum() const override { return Channels; }
    size_t GetSampleRate() const override { return Rate; }
    size_t GetTotalSamples() const override { return Total; }
    size_t Read(TPCMBuffer& buf, size_t sz) override {
        if (sz > Total - Pos)
            sz = Total - Pos;
        std::vector<int16_t> tmp(sz * Channels);
        size_t got = std::fread(tmp.data(), 2 * Channels, sz, F);
        float* out = buf[0];
        for (size_t i = 0; i < got * Channels; i++)
            out[i] = tmp[i] / 32768.0f;
        Pos += got;
        return got;
    }
    size_t Write(const TPCMBuffer&, size_t) override {
        throw std::runtime_error("WAV output is not supported by this build");
    }

private:
    std::FILE* F = nullptr;
    size_t Channels = 0, Rate = 0, Total = 0, Pos = 0;
};

IPCMProviderImpl* CreatePCMIOReadImpl(const std::string& path) {
    return new TPCMIORawWav(path);
}

IPCMProviderImpl* CreatePCMIOWriteImpl(const std::string&, int, int) {
    throw std::runtime_error("WAV output is not supported by this build");
}
