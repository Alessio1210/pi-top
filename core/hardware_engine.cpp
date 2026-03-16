#include <fcntl.h>
#include <iostream>
#include <string>
#include <termios.h>
#include <unistd.h>

// C++ ist blitzschnell beim Auslesen von seriellen Schnittstellen
int main() {
  // Öffne den UART-Port des pi-top
  int serial_port = open("/dev/serial0", O_RDWR);

  if (serial_port < 0) {
    std::cerr << "❌ Fehler: Konnte UART (/dev/serial0) nicht öffnen."
              << std::endl;
    return 1;
  }

  struct termios tty;
  if (tcgetattr(serial_port, &tty) != 0)
    return 1;

  tty.c_cflag &= ~PARENB; // Keine Parität
  tty.c_cflag &= ~CSTOPB; // 1 Stopp-Bit
  tty.c_cflag &= ~CSIZE;
  tty.c_cflag |= CS8; // 8 Bit
  cfsetispeed(&tty, B9600);
  cfsetospeed(&tty, B9600);
  tcsetattr(serial_port, TCSANOW, &tty);

  std::cout << "READY" << std::endl; // Signal an Python: Ich bin bereit!

  char read_buf[1];
  while (true) {
    int n = read(serial_port, &read_buf, sizeof(read_buf));
    if (n > 0) {
      unsigned char byte = (unsigned char)read_buf[0];

      // Mapping der Tasten (Seeed Studio Protokoll)
      std::string key = "";
      if (byte == 0xE1)
        key = "1";
      else if (byte == 0xE2)
        key = "2";
      else if (byte == 0xE3)
        key = "3";
      else if (byte == 0xE4)
        key = "4";
      else if (byte == 0xE5)
        key = "5";
      else if (byte == 0xE6)
        key = "6";
      else if (byte == 0xE7)
        key = "7";
      else if (byte == 0xE8)
        key = "8";
      else if (byte == 0xE9)
        key = "9";
      else if (byte == 0xEB)
        key = "0";
      else if (byte == 0xEA)
        key = "*";
      else if (byte == 0xEC)
        key = "#";

      if (!key.empty()) {
        // Wir schicken die Taste einfach an stdout,
        // Python liest das mit subprocess.readline()
        std::cout << "KEY:" << key << std::endl;
      }
    }
    usleep(1000); // 1ms Pause (Spart CPU, reagiert aber sofort)
  }

  close(serial_port);
  return 0;
}
