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

class PiTopCore {
private:
  int i2c_fd;
  int uart_fd;
  int lcd_addr = -1;
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
    int test_addresses[] = {0x3e, 0x27, 0x3f, 0x5a, 0x60};
    for (int addr : test_addresses) {
      if (ioctl(i2c_fd, I2C_SLAVE, addr) >= 0) {
        if (write(i2c_fd, NULL, 0) >= 0) {
          if (addr == 0x3e || addr == 0x27 || addr == 0x3f) {
            lcd_addr = addr;
            std::cout << "FOUND:LCD:" << std::hex << addr << std::endl;
          } else if (addr == 0x5a) {
            std::cout << "FOUND:KEYPAD:0x5a" << std::endl;
          }
        }
      }
    }
  }

  void initLCD() {
    auto sendCmd = [&](unsigned char cmd) {
      unsigned char buf[2] = {0x80, cmd};
      ioctl(i2c_fd, I2C_SLAVE, lcd_addr);
      write(i2c_fd, buf, 2);
    };
    usleep(50000);
    sendCmd(0x38); // Function set
    sendCmd(0x0C); // Display on
    sendCmd(0x01); // Clear
    usleep(2000);
  }

  void writeLCD(std::string l1, std::string l2) {
    if (lcd_addr == -1)
      return;

    auto sendCmd = [&](unsigned char cmd) {
      unsigned char buf[2] = {0x80, cmd};
      ioctl(i2c_fd, I2C_SLAVE, lcd_addr);
      write(i2c_fd, buf, 2);
    };
    auto sendData = [&](unsigned char data) {
      unsigned char buf[2] = {0x40, data};
      ioctl(i2c_fd, I2C_SLAVE, lcd_addr);
      write(i2c_fd, buf, 2);
    };

    sendCmd(0x01); // Clear
    usleep(2000);
    sendCmd(0x80);
    for (char c : l1.substr(0, 16))
      sendData(c);
    sendCmd(0xC0);
    for (char c : l2.substr(0, 16))
      sendData(c);
  }

  void commandListener() {
    std::string line;
    while (std::getline(std::cin, line)) {
      if (line.substr(0, 4) == "LCD:") {
        size_t sep = line.find('|');
        if (sep != std::string::npos) {
          writeLCD(line.substr(4, sep - 4), line.substr(sep + 1));
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
