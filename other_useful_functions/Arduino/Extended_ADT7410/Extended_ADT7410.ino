#include <ExtendedADT7410.h>
#include <Wire.h>

//ADT7410 13/16-bit digital temperature sensor
//RED (VDD): 2.7 ... 5.5V
//BROWN (GND): 0V
//Arduino uno, wires:
//PURPLE 1 (SCL): SCL (near AREF, should be equal to ANALOG5)
//PURPLE 2 (SDA): SDA (near AREF, should be equal to ANALOG4)
//wire A0 and A1 of ADT7410 to GND for sensor 1, A0 to +Vin and 
//A1 to GND for sensor 2 and A0 to GND and A1 to +Vin for sensor 3

ADT7410 sensor_ADT7410_1(0);
ADT7410 sensor_ADT7410_2(1);
ADT7410 sensor_ADT7410_3(2);
// variables for storing data temporarily:
unsigned int tempBytes[3] = {};
//float startTime = 0;
float timeStamp = 0;

void setup() {
  // Open serial communications and wait for port to open:
  Serial.begin(9600);
  while (!Serial) {
    Serial.println("Waiting..."); // wait for serial port to connect. Needed for native USB port only
  }
  pinMode(13, OUTPUT);
  
  sensor_ADT7410_1.initialise();
  sensor_ADT7410_2.initialise();
  sensor_ADT7410_3.initialise();
  
  //Serial.println("Setting 16-bit mode...");
  //startTime = millis();
}

void loop() {
  serialWrite(); //print on serial port
  delay(315);
}

void serialWrite()
{
  // light up when reading
  digitalWrite(13, HIGH);
  tempBytes[0] = sensor_ADT7410_1.readTemperature();
  tempBytes[1] = sensor_ADT7410_2.readTemperature();
  tempBytes[2] = sensor_ADT7410_3.readTemperature();
  delay(120);
  digitalWrite(13, LOW);

  timeStamp = millis();
  //int sum[] = {0, 0, 0};
 // for (int i = 0; i < 30; i+=3)
//  {
//    sum[0] += tempBytes[i];
//    sum[1] += tempBytes[i + 1];
//    sum[2] += tempBytes[i + 2];
//  }
//  
//  float avg0 = sum[0] / 10.0f;
//  float avg1 = sum[1] / 10.0f;
//  float avg2 = sum[2] / 10.0f;

  Serial.println("tx");
  delay(60);
  Serial.println(timeStamp);
  Serial.println(tempBytes[0]);
  Serial.println(tempBytes[1]);
  Serial.println(tempBytes[2]);
}
