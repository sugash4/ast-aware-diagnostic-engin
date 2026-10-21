/*
 * test_cases/type_mismatch.cpp
 * Demonstrates: invalid type assignment / narrowing conversion error
 *
 * Expected errors (G++):
 *   type_mismatch.cpp:35:20: error: cannot convert 'const char*' to 'int'
 *   type_mismatch.cpp:43:18: warning: narrowing conversion from 'double' to 'int'
 *
 * Compile with:
 *   python main.py g++ test_cases/type_mismatch.cpp -o /tmp/type_mismatch
 */

#include <iostream>
#include <string>

/* Sensor reading structure */
struct SensorReading {
    int   device_id;
    int   raw_value;
    float calibrated;
};

/*
 * calibrate() — converts raw ADC counts to engineering units.
 * BUG 1: assigns a string literal to an int field.
 * BUG 2: assigns a double literal to an int with narrowing conversion.
 */
SensorReading calibrate(int raw) {
    SensorReading r;

    r.device_id = "SENSOR_01";   /* line 35: ERROR — string literal → int */

    r.raw_value = raw;

    /* BUG 2: 3.14159 is double; assigning to int discards fractional part.
     * With -Werror=narrowing this becomes a hard error in C++11 and later.
     */
    r.calibrated = raw * 3.14159;  /* technically fine — float ← double is ok */
    r.raw_value  = raw * 3.14159;  /* line 43: narrowing double → int          */

    return r;
}

int main() {
    SensorReading s = calibrate(512);
    std::cout << "device_id  : " << s.device_id  << "\n";
    std::cout << "raw_value  : " << s.raw_value  << "\n";
    std::cout << "calibrated : " << s.calibrated << "\n";
    return 0;
}
