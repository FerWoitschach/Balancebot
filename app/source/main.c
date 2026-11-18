#define F_CPU 16000000UL

#include <avr/io.h>
#include <avr/interrupt.h>
#include <util/delay.h>
#include <stdlib.h>
#include <stdbool.h>
#include <stdio.h>
#include <string.h>
#include <math.h>

#define MPU6050_ADDR 0x68

#define PIN_R1 (1 << PB0)
#define PIN_R2 (1 << PB1)
#define PIN_L2 (1 << PB4)
#define PIN_L1 (1 << PB5)

int16_t ay_offset = 0;
float old_p       = 0;
float p           = 0;
float i_val       = 0;
float old_i       = 0;
float d_val       = 0;
float bp          = 0.0f;
float pwm         = 0;

void twi_init(void) {
	TWSR = 0x00;
	TWBR = 12;
	TWCR = (1 << TWEN);
}

void mpu_write_reg(uint8_t reg, uint8_t val) {
	TWCR = (1 << TWINT) | (1 << TWSTA) | (1 << TWEN);

	while (!(TWCR & (1 << TWINT)));

	TWDR = (MPU6050_ADDR << 1);
	TWCR = (1 << TWINT) | (1 << TWEN);

	while (!(TWCR & (1 << TWINT)));

	TWDR = reg;
	TWCR = (1 << TWINT) | (1 << TWEN);

	while (!(TWCR & (1 << TWINT)));

	TWDR = val;
	TWCR = (1 << TWINT) | (1 << TWEN);

	while (!(TWCR & (1 << TWINT)));

	TWCR = (1 << TWINT) | (1 << TWSTO) | (1 << TWEN);
}

void mpu_read_all(
	int16_t *ax,
	int16_t *ay,
	int16_t *az,
	int16_t *gx,
	int16_t *gy,
	int16_t *gz
) {
	TWCR = (1 << TWINT) | (1 << TWSTA) | (1 << TWEN);

	while (!(TWCR & (1 << TWINT)));

	TWDR = (MPU6050_ADDR << 1);
	TWCR = (1 << TWINT) | (1 << TWEN);

	while (!(TWCR & (1 << TWINT)));

	TWDR = 0x3B;
	TWCR = (1 << TWINT) | (1 << TWEN);

	while (!(TWCR & (1 << TWINT)));

	TWCR = (1 << TWINT) | (1 << TWSTA) | (1 << TWEN);

	while (!(TWCR & (1 << TWINT)));

	TWDR = (MPU6050_ADDR << 1) | 1;
	TWCR = (1 << TWINT) | (1 << TWEN);

	while (!(TWCR & (1 << TWINT)));

	uint8_t data[14]; for (uint8_t i = 0; i < 13; i++) {
		TWCR = (1 << TWINT) | (1 << TWEN) | (1 << TWEA);
		while (!(TWCR & (1 << TWINT)));
		data[i] = TWDR;
	}
	TWCR = (1 << TWINT) | (1 << TWEN);

	while (!(TWCR & (1 << TWINT)));

	data[13] = TWDR;

	TWCR = (1 << TWINT) | (1 << TWSTO) | (1 << TWEN);

	*ax = (int16_t)((data[0] << 8) | data[1]);
	*ay = (int16_t)((data[2] << 8) | data[3]);
	*az = (int16_t)((data[4] << 8) | data[5]);
	*gx = (int16_t)((data[8] << 8) | data[9]);
	*gy = (int16_t)((data[10] << 8) | data[11]);
	*gz = (int16_t)((data[12] << 8) | data[13]);
}

void uart_init(unsigned int baud) {
	unsigned int ubrr = F_CPU / 16 / baud - 1;

	UBRR0H = (unsigned char)(ubrr >> 8);
	UBRR0L = (unsigned char)ubrr;

	UCSR0B = (1 << TXEN0)  | (1 << RXEN0);
	UCSR0C = (1 << UCSZ01) | (1 << UCSZ00);
}

void uart_transmit(unsigned char data) {
	while (!(UCSR0A & (1 << UDRE0)));
	UDR0 = data;
}

void uart_print(const char* s) {
	while (*s) {
		uart_transmit(*s++);
	}
}

void setup(void) {
	DDRB  |=  (PIN_R1 | PIN_R2 | PIN_L1 | PIN_L2);
	PORTB &= ~(PIN_R1 | PIN_R2 | PIN_L1 | PIN_L2);
	DDRD  |=  (1 << PD5)    | (1 << PD6);
	TCCR0A =  (1 << COM0A1) | (1 << COM0B1) | (1 << WGM00) | (1 << WGM01);
	TCCR0B =  (1 << CS01)   | (1 << CS00);
	OCR0A  =  0;
	OCR0B  =  0;

	twi_init();
	uart_init(57600);

	for (uint8_t i = 0; i < 3; i++) {
		PORTB |=  (1 << PB5); _delay_ms(150);
		PORTB &= ~(1 << PB5); _delay_ms(150);
	}

	mpu_write_reg(0x6B, 0x00); _delay_ms(200);

	int32_t sum = 0;
	int16_t ax, ay, az, gx, gy, gz;

	for (int i = 0; i < 50; i++) {
		mpu_read_all(&ax, &ay, &az, &gx, &gy, &gz);
		sum += ay;
		_delay_ms(20);
	}

	ay_offset = (int16_t)(sum / 50);
	uart_print("[SETUP] OK\r\n");
}

int main(void) {
	setup();

	char buffer[64];

	int16_t ax, ay, az, gx, gy, gz;
	uint8_t divider = 0;

	while (1) {
		mpu_read_all(&ax, &ay, &az, &gx, &gy, &gz);

		int16_t ay_centered = ay - ay_offset;

		if (abs(ay_centered) < 100) {
			ay_centered = 0;
		}

		old_p = p;
		p = (float)ay_centered + bp;
		
		if (ay_centered == 0) {
			i_val *= 0.8f;
		} else {
			i_val = i_val + (p * 0.01f);
		}

		if (i_val > 100.0f)  i_val =  100.0f;
		if (i_val < -100.0f) i_val = -100.0f;
		
		d_val = p - old_p;
		pwm = (p * 0.08f) + i_val + (d_val * 0.4f) + ((float)gy * 0.002f);

		uint8_t dir = 0;

		if (pwm < 0) {
			dir = 1;

			PORTB &= ~PIN_R1; PORTB |= PIN_R2;
			PORTB &= ~PIN_L1; PORTB |= PIN_L2;
		} else {
			dir = 0;

			PORTB |= PIN_R1; PORTB &= ~PIN_R2;
			PORTB |= PIN_L1; PORTB &= ~PIN_L2;
		}

		float abs_pwm = fabsf(pwm);

		if (abs_pwm > 255.0f) abs_pwm = 255.0f;

		uint8_t pwm_val = (uint8_t)abs_pwm;

		if (abs(ay_centered) > 12000) {
			pwm_val = 0;
			PORTB &= ~(PIN_R1 | PIN_R2 | PIN_L1 | PIN_L2);
		}

		OCR0A = pwm_val;
		OCR0B = pwm_val;

		divider++; if (divider >= 20) {
			divider = 0;
			int len = snprintf(buffer, sizeof(buffer), "AY:%d | PID:%d | Dir:%d | PWM:%d\r\n", ay_centered, (int)pwm, dir, pwm_val);
			for (int i = 0; i < len; i++) {
				uart_transmit(buffer[i]);
			}
		}

		_delay_ms(300);
	}
	return 0;
}
