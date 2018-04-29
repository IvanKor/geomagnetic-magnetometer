/*
 * HMC5983.cpp - library header
 *
 * simple library for the HMC5983 sensor from Honeywell
 *
 */

#ifndef HMC5983_h
#define HMC5983_h

#if ARDUINO >= 100
#include "Arduino.h"
#include <Wire.h>
#else
#include "WProgram.h"
#endif

// I2C ADDRESS
#define HMC5983_ADDRESS 0x1E

// I2C COMMANDS
#define HMC5983_WRITE  0x3C
#define HMC5983_READ  0x3D

// MEMORY MAPPING
/*
Address Location  Name    Access
---------------------------------------------------
0x00  Configuration Register A  Read/Write
0x01  Configuration Register B  Read/Write
0x02  Mode Register     Read/Write
0x03  Data Output X MSB Register  Read
0x04  Data Output X LSB Register  Read
0x05  Data Output Z MSB Register  Read
0x06  Data Output Z LSB Register  Read
0x07  Data Output Y MSB Register  Read
0x08  Data Output Y LSB Register  Read
0x09  Status Register     Read
0x0A  Identification Register A Read
0x0B  Identification Register B Read
0x0C  Identification Register C Read
0x31  Temperature Output MSB Register Read
0x32  Temperature Output LSB Register Read
*/

#define HMC5983_REG_CONFIG_A (0x00)
#define HMC5983_REG_CONFIG_B (0x01)
#define HMC5983_REG_MODE     (0x02)

#define HMC5983_OUT_X_MSB (0x03)
#define HMC5983_OUT_X_LSB (0x04)
#define HMC5983_OUT_Z_MSB (0x05)
#define HMC5983_OUT_Z_LSB (0x06)
#define HMC5983_OUT_Y_MSB (0x07)
#define HMC5983_OUT_Y_LSB (0x08)

#define HMC5983_STATUS (0x09)

#define HMC5983_TEMP_OUT_MSB (0x31)
#define HMC5983_TEMP_OUT_LSB (0x32)

#define HMC5983_REG_OUT_X_M (0x03)
#define HMC5983_REG_OUT_X_L (0x04)
#define HMC5983_REG_OUT_Z_M (0x05)
#define HMC5983_REG_OUT_Z_L (0x06)
#define HMC5983_REG_OUT_Y_M (0x07)
#define HMC5983_REG_OUT_Y_L (0x08)

#define HMC5983_REG_IDENT_A (0x0A)
#define HMC5983_REG_IDENT_B (0x0B)
#define HMC5983_REG_IDENT_C (0x0C)

typedef enum {
  HMC5983_DATARATE_220HZ      = 0b111,
  HMC5983_DATARATE_75HZ       = 0b110,
  HMC5983_DATARATE_30HZ       = 0b101,
  HMC5983_DATARATE_15HZ       = 0b100,
  HMC5983_DATARATE_7_5HZ      = 0b011,
  HMC5983_DATARATE_3HZ        = 0b010,
  HMC5983_DATARATE_1_5HZ      = 0b001,
  HMC5983_DATARATE_0_75HZ     = 0b000
} hmc5983_dataRate_t;

typedef enum {
  HMC5983_SAMPLEAVERAGE_8     = 0b11,
  HMC5983_SAMPLEAVERAGE_4     = 0b10,
  HMC5983_SAMPLEAVERAGE_2     = 0b01,
  HMC5983_SAMPLEAVERAGE_1     = 0b00
} hmc5983_sampleAverages_t;

typedef enum {
  HMC5983_RANGE_8_1GA     = 0b111,
  HMC5983_RANGE_5_6GA     = 0b110,
  HMC5983_RANGE_4_7GA     = 0b101,
  HMC5983_RANGE_4GA       = 0b100,
  HMC5983_RANGE_2_5GA     = 0b011,
  HMC5983_RANGE_1_9GA     = 0b010,
  HMC5983_RANGE_1_3GA     = 0b001,
  HMC5983_RANGE_0_88GA    = 0b000
} hmc5983_range_t;

typedef enum {
  HMC5983_IDLE1         = 0b11,
  HMC5983_IDLE2         = 0b10,
  HMC5983_SINGLE        = 0b01,
  HMC5983_CONTINOUS     = 0b00
} hmc5983_mode_t;

class HMC5983 {
  public:
    bool begin(void (*ISR_callback)() = NULL, int D = false);
    
    void  setRange(hmc5983_range_t range);
    hmc5983_range_t getRange(void);
    void  setMeasurementMode(hmc5983_mode_t mode);
    hmc5983_mode_t getMeasurementMode(void);
    void  setDataRate(hmc5983_dataRate_t dataRate);
    hmc5983_dataRate_t getDataRate(void);
    void setSampleAverages(hmc5983_sampleAverages_t sampleAverages);
    hmc5983_sampleAverages_t getSampleAverages(void);
    
  private:
    void writeRegister8(uint8_t reg, uint8_t value);
    uint8_t readRegister8(uint8_t reg);
    uint8_t fastRegister8(uint8_t reg);
    int16_t readRegister16(uint8_t reg);
    int DEBUG;
};

#endif
