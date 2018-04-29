#include "HMC5983.h"


HMC5983 compass;
boolean compass_rdy = false;
int counter = 0;
byte X_MSB ;
byte X_LSB ;
byte Z_MSB ;
byte Z_LSB ;
byte Y_MSB ;
byte Y_LSB ;
int HiX;
int HiY;
int HiZ;


void readCompass_ISR() {
  compass_rdy = true;
  //counter ++;
}

void setup() {
  // put your setup code here, to run once:
//  Serial.begin(250000); // this is going to be hot... :)
//  Serial.begin(2000000); // this is going to be hot... :)
//  Serial.begin(230400); // this is going to be hot... :)
  Serial.begin(38400); // this is going to be hot... :)
  
  while (!compass.begin(readCompass_ISR, 0)) {
    Serial.println("HMC5983 Problem");
    delay(500);
  }  
}


void loop() {

  if (compass_rdy) {
    compass_rdy = false;
    Wire.beginTransmission(HMC5983_ADDRESS);
    Wire.write(HMC5983_REG_OUT_X_M);
    Wire.requestFrom(HMC5983_ADDRESS, 6);
     X_MSB = Wire.read();
    X_LSB = Wire.read();
    Z_MSB = Wire.read();
    Z_LSB = Wire.read();
    Y_MSB = Wire.read();
    Y_LSB = Wire.read();
    Wire.endTransmission();
    // compose byte for X, Y, Z's LSB & MSB 8bit registers
    //HiX = (X_MSB << 8) + X_LSB;
    HiZ = (Z_MSB << 8) + Z_LSB;
    //HiY = (Y_MSB << 8) + Y_LSB;
    if (!counter){
      Serial.flush(); 
      Serial.println(String(HiZ, DEC));
    }else{
      counter -=1;
    }
  }else{
    //delay(1); 
    //delayMicroseconds(500);
    if ( Serial.available() > 0 ) {
    // Read the incoming byte
      char theChar = Serial.read();
      // Parse character
      switch (theChar) {
          case 's':
            counter =2;
            compass.setRange(HMC5983_RANGE_0_88GA);          
          break;
          case 'S':     
            counter =2;
            compass.setRange(HMC5983_RANGE_8_1GA);
          break;
      }
    }
  }
}
