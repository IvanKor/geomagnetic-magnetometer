/*
 * HMC5983.cpp - library class
 * 
 */

#include "HMC5983.h"


bool HMC5983::begin(void (*ISR_callback)(), int D){

  DEBUG = D;

  Wire.begin();
  Wire.setClock(400000);
  //Wire.setClock(100000);
  
  if ((fastRegister8(HMC5983_REG_IDENT_A) != 0x48)
    || (fastRegister8(HMC5983_REG_IDENT_B) != 0x34)
    || (fastRegister8(HMC5983_REG_IDENT_C) != 0x33)) {
    return false;
  }

  // set Gain Range
  //setRange(HMC5983_RANGE_8_1GA);
  setRange(HMC5983_RANGE_0_88GA);

  // Set DataRate 220Hz ~4.5ms
  setDataRate(HMC5983_DATARATE_220HZ);

  // Set number of samples to average
  setSampleAverages(HMC5983_SAMPLEAVERAGE_1);
  // Set Mode
  setMeasurementMode(HMC5983_CONTINOUS | 0x80);//temperature ON


  // Setup DRDY int
  if (ISR_callback != NULL) {
  //pinMode(3, INPUT_PULLUP);
    pinMode(3, INPUT);
    attachInterrupt(digitalPinToInterrupt(3), ISR_callback, RISING );
  }

  return true;
}


void HMC5983::setRange(hmc5983_range_t range) {

    writeRegister8(HMC5983_REG_CONFIG_B, range << 5);
}

void HMC5983::setMeasurementMode(hmc5983_mode_t mode) {
    uint8_t value;

    value = readRegister8(HMC5983_REG_MODE);
    value &= 0b11111100;
    value |= mode;

    writeRegister8(HMC5983_REG_MODE, value);
}

void HMC5983::setDataRate(hmc5983_dataRate_t dataRate) {
    uint8_t value;

    value = readRegister8(HMC5983_REG_CONFIG_A);
    value &= 0b11100011;
    value |= (dataRate << 2);

    writeRegister8(HMC5983_REG_CONFIG_A, value);
}


void HMC5983::setSampleAverages(hmc5983_sampleAverages_t sampleAverages) {
    uint8_t value;

    value = readRegister8(HMC5983_REG_CONFIG_A);
    value &= 0b10011111;
    value |= (sampleAverages << 5);

    writeRegister8(HMC5983_REG_CONFIG_A, value);
}


// Write byte to register
void HMC5983::writeRegister8(uint8_t reg, uint8_t value) {
  Wire.beginTransmission(HMC5983_ADDRESS);
  #if ARDUINO >= 100
      Wire.write(reg);
      Wire.write(value);
  #else
      Wire.send(reg);
      Wire.send(value);
  #endif
  Wire.endTransmission();
}

// Read byte to register
uint8_t HMC5983::fastRegister8(uint8_t reg) {
  uint8_t value;
  Wire.beginTransmission(HMC5983_ADDRESS);
  #if ARDUINO >= 100
      Wire.write(reg);
  #else
      Wire.send(reg);
  #endif
  Wire.endTransmission();

  Wire.requestFrom(HMC5983_ADDRESS, 1);
  #if ARDUINO >= 100
      value = Wire.read();
  #else
      value = Wire.receive();
  #endif;
  Wire.endTransmission();

  return value;
}

// Read byte from register
uint8_t HMC5983::readRegister8(uint8_t reg) {
  uint8_t value;
  Wire.beginTransmission(HMC5983_ADDRESS);
  Wire.write(reg);
  Wire.endTransmission();
  Wire.beginTransmission(HMC5983_ADDRESS);
  Wire.requestFrom(HMC5983_ADDRESS, 1);
  while(!Wire.available()) {};
  value = Wire.read();
  Wire.endTransmission();
  return value;
}


