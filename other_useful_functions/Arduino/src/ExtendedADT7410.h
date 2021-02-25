/* 
 ADT7410 Temperature Sensor Library
 By: Geoffrey Van Landeghem
 Edited by: Maxwell Guerne-Kieferndorf
 Date: February 23nd, 2017
        December 3rd, 2020 resp.
 License: This code is public domain but you buy me a beer if you use this and we meet someday (Beerware license).
 
 Get temperature from the ADT7410 sensor.
 
 */

#ifndef EasyADT7410_h
#define EasyADT7410_h

#define ADT7410_I2C_ADDRESS_0 0x48 ///< first available I2C address
//#define ADT7410_I2C_ADDRESS_2 0x49  ///< second available I2C address
//#define ADT7410_I2C_ADDRESS_3 0x4A  ///< third available I2C address

#define ADT7410_REG__TEMP_MSB 0x00      ///< Temp. MSB register
#define ADT7410_REG__TEMP_LSB 0x01      ///< Temp. LSB register
#define ADT7410_REG__ADT7410_STATUS 0x2 ///< Status register
#define ADT7410_REG__CONFIG 0x03        ///< Configuration register
#define ADT7410_REG__ADT7410_ID 0xB     ///< Manufacturer identification

#define ADT7410_MODE_16BIT 0x80
#define ADT7410_MODE_FAULTQUEUE_DEF 0x00
#define ADT7410_MODE_FAULTQUEUE_4 0x03
#define ADT7410_MODE_CONTINUOUS 0x00
#define ADT7410_MODE_ONE_SPS 0x40
#define ADT7410_MODE_ONESHOT 0x20
#define ADT7410_MODE_SHUTDOWN 0x60

#include <Arduino.h>
#include <Wire.h>

class ADT7410
{
public:
    ADT7410(unsigned char); // should be 0,1 or 2 (initialisation with address)
    unsigned char initialise(void);
    unsigned short readTemperature(void);
    void set16bitMode(void);
    unsigned char getStatus(void);
    unsigned char getID(void);

private:
    unsigned char sensorID{0};      // should be 0,1 or 2
    unsigned char i2cAddress{0x48}; // first possible address is 0x48, corresponding to sensor 0
    void writeI2c(unsigned char, unsigned char);
    void readI2c(unsigned char, unsigned char, unsigned char *);
};

#endif
