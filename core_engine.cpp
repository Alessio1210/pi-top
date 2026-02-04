#include <fcntl.h>
#include <iostream>
#include <linux/i2c-dev.h>
#include <string>
#include <sys/ioctl.h>
#include <termios.h>
#include <thread>
#include <unistd.h>

// Hardware Adressen
#define LCD_ADDR 0x3e

class PiTopCore {
private:
  int i2c_fd;
  int uart_fd;
  std::string last_l1, last_l2;

public:
  PiTopCore() : i2c_fd(-1), uart_fd(-1) {
    initI2C();
    initUART();
    writeLCD("System startet", "Bitte warten...");
  }

  void initI2C() {
    i2c_fd = open("/dev/i2c-1", O_RDWR);
    if (i2c_fd < 0)
      std::cerr << "⚠️ Fehler: I2C Bus konnte nicht geöffnet werden."
                << std::endl;
  }

  void initUART() {
    uart_fd = open("/dev/serial0", O_RDWR | O_NOCTTY | O_NDELAY);
    if (uart_fd >= 0) {
      struct termios tty;
      tcgetattr(uart_fd, &tty);
      cfsetispeed(&tty, B9600);
      cfsetospeed(&tty, B9600);
      tty.c_cflag |= (CLOCAL | CREAD);
      tty.c_cflag &= ~PARENB;
      tty.c_cflag &= ~CSTOPB;
      tty.c_cflag &= ~CSIZE;
      tty.c_cflag |= CS8;
      tcsetattr(uart_fd, TCSANOW, &tty);
    }
  }

  void writeLCD(std::string l1, std::string l2) {
    if (i2c_fd < 0)
      return;
    if (l1 == last_l1 && l2 == last_l2)
      return;

    last_l1 = l1;
    last_l2 = l2;
    std::cout << "📟 [LCD] " << l1 << " | " << l2 << std::endl;

    // Grove LCD Initialisierung und Schreib-Befehle
    auto sendCmd = [&](unsigned char cmd) {
      unsigned char buf[2] = {0x80, cmd};
      ioctl(i2c_fd, I2C_SLAVE, LCD_ADDR);
      write(i2c_fd, buf, 2);
    };

    auto sendData = [&](unsigned char data) {
      unsigned char buf[2] = {0x40, data};
      ioctl(i2c_fd, I2C_SLAVE, LCD_ADDR);
      write(i2c_fd, buf, 2);
    };

    sendCmd(0x01); // Clear
    usleep(2000);
    sendCmd(0x80); // Line 1
    for (char c : l1.substr(0, 16))
      sendData(c);
    sendCmd(0xC0); // Line 2
    for (char c : l2.substr(0, 16))
      sendData(c);
  }

  void loop() {
    unsigned char read_buf[1];
    while (true) {
      // 1. Nachrichten von Python lesen (via stdin)
      // Hier könnten Befehle wie "SHOW:Name" kommen

      // 2. Keypad (UART) lesen
      if (uart_fd >= 0) {
        int n = read(uart_fd, &read_buf, 1);
        if (n > 0) {
          unsigned char b = read_buf[0];
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
      }
      usleep(10000);
    }
  }
};

int main() {
  PiTopCore core;
  core.loop();
  return 0;
}
