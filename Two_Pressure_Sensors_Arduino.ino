/*
  Two Honeywell ABP2MANT010BAAA5XX pressure sensors
  Arduino Mega 2560

  Wiring:
    Sensor 1: VDD -> 5 V, GND -> GND, VOUT -> A0
    Sensor 2: VDD -> 5 V, GND -> GND, VOUT -> A1

  Serial CSV format:
    Time_s,ADC1,Pressure1_bar,ADC2,Pressure2_bar,Difference_bar

  The conversion assumes a 0-10 bar sensor with analog output spanning
  10%-90% of its supply. Because the sensors and the ATmega2560 ADC use the
  same 5 V rail, the count-based conversion is ratiometric.
*/

const byte PRESSURE_PIN_1 = A0;
const byte PRESSURE_PIN_2 = A1;

const unsigned long BAUD_RATE = 115200;
const unsigned long REPORT_INTERVAL_MS = 100;  // 10 recorded rows per second
const byte NUM_SAMPLES = 20;

const float PRESSURE_MIN_BAR = 0.0;
const float PRESSURE_MAX_BAR = 10.0;

// Separate constants make later two-point calibration easy.
const float SENSOR_1_ADC_AT_0_BAR = 102.3;   // 10% of 1023
const float SENSOR_1_ADC_AT_10_BAR = 920.7;  // 90% of 1023
const float SENSOR_2_ADC_AT_0_BAR = 102.3;
const float SENSOR_2_ADC_AT_10_BAR = 920.7;

unsigned long startTimeMs;
unsigned long previousReportMs;


float readAveragedAdc(byte pin)
{
  unsigned long sum = 0;

  // Discard the first reading after selecting a different ADC channel.
  analogRead(pin);
  delayMicroseconds(200);

  for (byte i = 0; i < NUM_SAMPLES; i++)
  {
    sum += analogRead(pin);
    delayMicroseconds(500);
  }

  return sum / (float)NUM_SAMPLES;
}


float adcToPressure(float adcValue, float adcAtMinimum, float adcAtMaximum)
{
  return PRESSURE_MIN_BAR
         + (adcValue - adcAtMinimum)
         * (PRESSURE_MAX_BAR - PRESSURE_MIN_BAR)
         / (adcAtMaximum - adcAtMinimum);
}


void setup()
{
  Serial.begin(BAUD_RATE);
  analogReference(DEFAULT);
  delay(500);

  startTimeMs = millis();
  previousReportMs = startTimeMs;

  Serial.println(
    F("Time_s,ADC1,Pressure1_bar,ADC2,Pressure2_bar,Difference_bar")
  );
}


void loop()
{
  const unsigned long now = millis();

  if (now - previousReportMs < REPORT_INTERVAL_MS)
  {
    return;
  }

  // Advance by a fixed interval to reduce timing drift.
  previousReportMs += REPORT_INTERVAL_MS;

  const float adc1 = readAveragedAdc(PRESSURE_PIN_1);
  const float adc2 = readAveragedAdc(PRESSURE_PIN_2);

  const float pressure1 = adcToPressure(
    adc1, SENSOR_1_ADC_AT_0_BAR, SENSOR_1_ADC_AT_10_BAR
  );
  const float pressure2 = adcToPressure(
    adc2, SENSOR_2_ADC_AT_0_BAR, SENSOR_2_ADC_AT_10_BAR
  );
  const float difference = pressure1 - pressure2;
  const float elapsedSeconds = (now - startTimeMs) / 1000.0;

  Serial.print(elapsedSeconds, 3);
  Serial.print(',');
  Serial.print(adc1, 2);
  Serial.print(',');
  Serial.print(pressure1, 4);
  Serial.print(',');
  Serial.print(adc2, 2);
  Serial.print(',');
  Serial.print(pressure2, 4);
  Serial.print(',');
  Serial.println(difference, 4);
}
