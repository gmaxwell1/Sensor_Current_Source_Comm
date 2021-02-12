/* 
 ADT7410 Temperature Sensor Library
 By: Geoffrey Van Landeghem
 Edited: Maxwell Guerne-Kieferndorf
 Date: February 23nd, 2017
        December 3rd, 2020
 License: This code is public domain but you buy me a beer if you use this and we meet someday (Beerware license).

 Part of the code is based on FaBo's ADT7410 library for Arduino.
    Released under APACHE LICENSE, VERSION 2.0
    http://www.apache.org/licenses/
    @author FaBo<info@fabo.io>

 Get temperature from the ADT7410 sensor, or from multiple Sensors.
 
 */

#include <ExtendedADT7410.h>

/**
    Up to 3 sensors may be initialized. Their addresses correspond to their ID.
*/
ADT7410::ADT7410(unsigned char sensor_id = 0)
{
    if (sensor_id == 0 || sensor_id == 1 || sensor_id == 2)
    {
        sensorID = sensor_id;
        i2cAddress = ADT7410_I2C_ADDRESS_0 + sensor_id;
    }
    else
    {
        sensorID = 0;
        i2cAddress = ADT7410_I2C_ADDRESS_0;
    }
}

/**
 @brief initialise and configure sensor settings to 16bit accuracy and otherwise default modes
 @return Sensor ID (contents of ID register)
*/
unsigned char ADT7410::initialise(void)
{
    Wire.begin();

    unsigned char whoami;
    readI2c(ADT7410_REG__ADT7410_ID, 1, &whoami);

    uint8_t config = ADT7410_MODE_16BIT;
    config |= ADT7410_MODE_CONTINUOUS;
    //config |= ADT7410_MODE_FAULTQUEUE_DEF;
    config |= 0b00000001; // 2 faults allowed in fault queue
    writeI2c(ADT7410_REG__CONFIG, config);

    return whoami;
}

unsigned char ADT7410::getID(void)
{
    return sensorID;
}

/**
    @brief reads temperature bytes from Sensor over I2C.
    @return raw temperature bytes, value between 0 and 65536

    @note conversion to temperature values: 
    if value > 32768:
        value = value - 65536
    temp = value/128.0

    accuracy of temp is 0.0078(125)
*/
unsigned short ADT7410::readTemperature(void)
{
    unsigned char data[2];
    unsigned short tempValue = 0;
    unsigned char config = 0;

    // check if data is ready, i.e. if status[7] is low
    unsigned char status = getStatus();
    if (!(status & 0x80))
    {
        readI2c(ADT7410_REG__CONFIG, 1, &config);
        readI2c(ADT7410_REG__TEMP_MSB, 2, data);

        //concat MSB&LSB
        tempValue = (unsigned short)data[0] << 8;
        tempValue |= data[1];

        if (config & 0x80)
        {
            // 13bit resolution
            tempValue >>= 3;
            // check sign bit
            if (tempValue & 0x1000)
                tempValue = tempValue - 8192;
        }
        else
        {
            // 16bit resolution
            // check sign bit
            if (tempValue & 0x8000)
                tempValue = tempValue - 65536;
        }
    }
    return tempValue;
}

/**
 @brief Status Check
 @return contents of status register (address 0x02)
*/
unsigned char ADT7410::getStatus(void)
{
    unsigned char status;
    readI2c(ADT7410_REG__ADT7410_STATUS, 1, &status);
    // bits [3:0] are always 0. bits [6:4] go high when temp exceeds Tcrit, Thigh or goes below Tlow respectively.
    // bit 7 is 1 by default and is set to 0 when a temp conversion result is written into the temp value register.
    return status;
}

/**
 @brief Write I2C
 @param [in] address register address
 @param [in] data write data
*/
void ADT7410::writeI2c(unsigned char address, unsigned char data)
{
    Wire.beginTransmission(i2cAddress);
    Wire.write(address);
    Wire.write(data);
    Wire.endTransmission();
}

/**
 @brief Read I2C
 @param [in] address register address
 @param [in] num read length
 @param [out] data read data
*/
void ADT7410::readI2c(unsigned char address, unsigned char num, unsigned char *data)
{
    Wire.beginTransmission(i2cAddress);
    Wire.write(address);
    Wire.endTransmission();
    uint8_t i = 0;
    Wire.requestFrom(i2cAddress, num);
    while (Wire.available())
    {
        data[i++] = Wire.read();
    }
}