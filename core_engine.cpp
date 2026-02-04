#include <fcntl.h>
#include <iostream>
#include <linux/i2c-dev.h>
#include <string>
#include <sys/ioctl.h>
#include <termios.h>
#include <thread>
#include <unistd.h>
#include <vector>

// I2C Adressen
#define GROVE_LCD_ADDR 0x3e
#define GENERIC_LCD_ADDR 0x27
#define RGB_ADDR 0x62

class PiTopCore {
private:
  int i2c_fd;
  int uart_fd;
  int lcd_addr = -1;
  bool has_rgb = false;
  std::string current_l1, current_l2;

public:
  PiTopCore() {
    initI2C();
    initUART();
    scanHardware();

    if (lcd_addr != -1) {
      initLCD();
      writeLCD("C++ Core ready", "Waiting for App");
    }
    std::cout << "READY" << std::endl;
  }

  void initI2C() { i2c_fd = open("/dev/i2c-1", O_RDWR); }

  void initUART() {
    uart_fd = open("/dev/serial0", O_RDWR | O_NOCTTY);
    if (uart_fd >= 0) {
      struct termios tty;
      tcgetattr(uart_fd, &tty);
      cfsetispeed(&tty, B9600);
      cfsetospeed(&tty, B9600);
      tty.c_cflag |= (CLOCAL | CREAD | CS8);
      tty.c_cflag &= ~(PARENB | CSTOPB);
      tcsetattr(uart_fd, TCSANOW, &tty);
    }
  }

  void scanHardware() {
    // Schneller I2C Scan
    int addresses[] = {0x3e, 0x27, 0x3f, 0x62, 0x5a};
    for (int addr : addresses) {
      if (ioctl(i2c_fd, I2C_SLAVE, addr) >= 0) {
        if (write(i2c_fd, NULL, 0) >= 0) {
          if (addr == 0x3e || addr == 0x27 || addr == 0x3f) {
            lcd_addr = addr;
            std::cout << "FOUND:LCD:" << std::hex << addr << std::endl;
          } else if (addr == 0x62) {
            has_rgb = true;
            std::cout << "FOUND:RGB:0x62" << std::endl;
          } else if (addr == 0x5a) {
            std::cout << "FOUND:KEYPAD:0x5a" << std::endl;
          }
        }
      }
    }
  }

  void initLCD() {
    if (lcd_addr == -1)
      return;
    ioctl(i2c_fd, I2C_SLAVE, lcd_addr);

    if (lcd_addr == 0x3e) { // Grove LCD Protocol
      auto sendCmd = [&](unsigned char cmd) {
        unsigned char buf[2] = {0x80, cmd};
        write(i2c_fd, buf, 2);
      };
      usleep(50000);
      sendCmd(0x38);
      usleep(50);
      sendCmd(0x0C);
      usleep(50);
      sendCmd(0x01);
      usleep(2000);
    } else { // Generic PCF8574 LCD Protocol (White/Blue)
      auto writeNibble = [&](unsigned char n) {
        unsigned char buf[1];
        buf[0] = n | 0x08 | 0x04; // Backlight=1, Enable=1
        write(i2c_fd, buf, 1);
        usleep(1);
        buf[0] = (n | 0x08) & ~0x04; // Enable=0
        write(i2c_fd, buf, 1);
        usleep(50);
      };
      auto sendByte = [&](unsigned char val, int mode) {
        unsigned char hn = (val & 0xF0) | mode;
        unsigned char ln = ((val << 4) & 0xF0) | mode;
        writeNibble(hn);
        writeNibble(ln);
      };
      usleep(50000);
      writeNibble(0x30);
      usleep(4500);
      writeNibble(0x30);
      usleep(4500);
      writeNibble(0x30);
      usleep(150);
      writeNibble(0x20); // 4-bit mode
      sendByte(0x28, 0); // 2 lines
      sendByte(0x0C, 0); // Display on
      sendByte(0x01, 0); // Clear
      usleep(2000);
    }

    if (has_rgb) {
      setLCDColor(255, 255, 255);
    }
  }

  void setLCDColor(int r, int g, int b) {
    if (!has_rgb)
      return;
    ioctl(i2c_fd, I2C_SLAVE, RGB_ADDR);
    auto sendRGB = [&](unsigned char reg, unsigned char val) {
      unsigned char buf[2] = {reg, val};
      write(i2c_fd, buf, 2);
    };
    sendRGB(0x00, 0x00);
    sendRGB(0x08, 0xAA);
    sendRGB(0x04, r);
    sendRGB(0x03, g);
    sendRGB(0x02, b);
  }

  void writeLCD(std::string l1, std::string l2) {
    if (lcd_addr == -1)
      return;
    ioctl(i2c_fd, I2C_SLAVE, lcd_addr);

    if (lcd_addr == 0x3e) { // Grove
      auto sendCmd = [&](unsigned char cmd) {
        unsigned char buf[2] = {0x80, cmd};
        write(i2c_fd, buf, 2);
      };
      auto sendData = [&](unsigned char data) {
        unsigned char buf[2] = {0x40, data};
        write(i2c_fd, buf, 2);
      };
      sendCmd(0x01);
      usleep(2000);
      sendCmd(0x80);
      for (char c : l1.substr(0, 16))
        sendData(c);
      sendCmd(0xC0);
      for (char c : l2.substr(0, 16))
        sendData(c);
    } else { // Generic PCF8574
      auto writeNibble = [&](unsigned char n) {
        unsigned char buf[1];
        buf[0] = n | 0x08 | 0x04;
        write(i2c_fd, buf, 1);
        usleep(1);
        buf[0] = (n | 0x08) & ~0x04;
        write(i2c_fd, buf, 1);
        usleep(50);
      };
      auto sendByte = [&](unsigned char val, int mode) {
        unsigned char hn = (val & 0xF0) | mode;
        unsigned char ln = ((val << 4) & 0xF0) | mode;
        writeNibble(hn);
        writeNibble(ln);
      };
      sendByte(0x01, 0);
      usleep(2000);
      sendByte(0x80, 0);
      for (char c : l1.substr(0, 16))
        sendByte(c, 1);
      sendByte(0xC0, 0);
      for (char c : l2.substr(0, 16))
        sendByte(c, 1);
    }
  }

  void commandListener() {
    std::string line;
    while (std::getline(std::cin, line)) {
      if (line.substr(0, 4) == "LCD:") {
        size_t sep = line.find('|');
        if (sep != std::string::npos) {
          writeLCD(line.substr(4, sep - 4), line.substr(sep + 1));
        }
      } else if (line.substr(0, 4) == "RGB:") {
        int r, g, b;
        if (sscanf(line.c_str(), "RGB:%d,%d,%d", &r, &g, &b) == 3) {
          setLCDColor(r, g, b);
        }
      }
    }
  }

  void uartListener() {
    unsigned char b;
    while (true) {
      if (read(uart_fd, &b, 1) > 0) {
        std::string key = "";
        if (b == 0xE1)
          key = "1";
        else if (b == 0xE2)
          key = "2";
        else if (b == 0xE3)
          key = "3";
        else if (b == 0xE4)
          key = "4";
        else if (b == 0xE5)
          key = "5";
        else if (b == 0xE6)
          key = "6";
        else if (b == 0xE7)
          key = "7";
        else if (b == 0xE8)
          key = "8";
        else if (b == 0xE9)
          key = "9";
        else if (b == 0xEB)
          key = "0";
        else if (b == 0xEA)
          key = "*";
        else if (b == 0xEC)
          key = "#";
        if (!key.empty())
          std::cout << "KEY:" << key << std::endl;
      }
      usleep(10000);
    }
  }
};

int main() {
  PiTopCore core;
  std::thread t1(&PiTopCore::commandListener, &core);
  std::thread t2(&PiTopCore::uartListener, &core);
  t1.join();
  t2.join();
  return 0;
}
