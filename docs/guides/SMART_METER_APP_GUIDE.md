# Smart Meter Reading App - Complete Development Guide

## Overview

This guide will help you build a smart meter reading app (Android/Web/IoT device) that integrates with the Balilihan Waterworks Management System for accurate automated meter reading and billing.

---

## Table of Contents

1. [System Architecture](#system-architecture)
2. [API Endpoints Reference](#api-endpoints-reference)
3. [Android App Development](#android-app-development)
4. [IoT Smart Meter Integration](#iot-smart-meter-integration)
5. [Sample Code](#sample-code)
6. [Testing Guide](#testing-guide)

---

## System Architecture

```
┌─────────────────────┐
│  Smart Meter Device │
│  (Arduino/ESP32)    │
└──────────┬──────────┘
           │ WiFi/GSM
           ▼
┌─────────────────────┐     HTTPS      ┌──────────────────────┐
│   Mobile App        │────────────────▶│  Waterworks API      │
│   (Android/iOS)     │◀────────────────│  (Vercel + Neon DB)  │
└─────────────────────┘                 └──────────────────────┘
           │                                      │
           ▼                                      ▼
    Field Staff                           Web Dashboard
    (Data Review)                        (Admin Confirmation)
```

---

## API Endpoints Reference

### Base URL
- **Production**: `https://waterworks-rose.vercel.app`
- **Local**: `http://localhost:8000`

### Required Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/login/` | POST | Authenticate field staff |
| `/api/consumers/` | GET | Get all consumers with previous readings |
| `/api/consumers/<id>/previous-reading/` | GET | Get specific consumer's last reading |
| `/api/rates/` | GET | Get current tiered water rates |
| `/api/meter-readings/` | POST | Submit new meter reading |
| `/api/logout/` | POST | End session |

---

## Android App Development

### Step 1: Project Setup

#### build.gradle (app level)
```gradle
dependencies {
    // Networking
    implementation 'com.squareup.retrofit2:retrofit:2.9.0'
    implementation 'com.squareup.retrofit2:converter-gson:2.9.0'
    implementation 'com.squareup.okhttp3:okhttp:4.11.0'
    implementation 'com.squareup.okhttp3:logging-interceptor:4.11.0'

    // UI
    implementation 'androidx.recyclerview:recyclerview:1.3.2'
    implementation 'com.google.android.material:material:1.10.0'
    implementation 'androidx.cardview:cardview:1.0.0'

    // JSON
    implementation 'com.google.code.gson:gson:2.10.1'
}
```

### Step 2: Create Data Models

See complete Java code in: `docs/sample_code/android/ApiModels.java`

#### models/Consumer.java
```java
public class Consumer(
    val id: Int,
    val account_number: String,
    val name: String,
    val serial_number: String,
    val status: String,
    val is_active: Boolean,
    val usage_type: String,  // "Residential" or "Commercial" - CRITICAL!
    val latest_confirmed_reading: Int,
    val previous_reading: Int,
    val is_delinquent: Boolean,
    val pending_bills_count: Int
)
```

#### models/WaterRates.kt
```kotlin
data class WaterRates(
    val status: String,
    val residential: RateTier,
    val commercial: RateTier,
    val tier_brackets: Map<String, String>,
    val updated_at: String
)

data class RateTier(
    val minimum_charge: Double,
    val tier2_rate: Double,
    val tier3_rate: Double,
    val tier4_rate: Double,
    val tier5_rate: Double
)
```

#### models/ReadingSubmission.kt
```kotlin
data class ReadingSubmission(
    val consumer_id: Int,
    val reading_value: Int,
    val reading_date: String,  // Format: "YYYY-MM-DD"
    val source: String = "mobile_app"  // or "smart_meter"
)

data class ReadingResponse(
    val status: String,
    val message: String,
    val reading_id: Int?,
    val consumer: String?,
    val reading_value: Int?,
    val consumption: Int?,
    val estimated_bill: Double?
)
```

### Step 3: Network Layer

#### api/ApiService.kt
```kotlin
interface ApiService {
    @POST("api/login/")
    suspend fun login(@Body credentials: LoginRequest): Response<LoginResponse>

    @GET("api/consumers/")
    suspend fun getConsumers(): Response<List<Consumer>>

    @GET("api/consumers/{id}/previous-reading/")
    suspend fun getPreviousReading(@Path("id") consumerId: Int): Response<PreviousReading>

    @GET("api/rates/")
    suspend fun getCurrentRates(): Response<WaterRates>

    @POST("api/meter-readings/")
    suspend fun submitReading(@Body reading: ReadingSubmission): Response<ReadingResponse>

    @POST("api/logout/")
    suspend fun logout(): Response<LogoutResponse>
}
```

#### api/RetrofitClient.kt
```kotlin
object RetrofitClient {
    private const val BASE_URL = "https://waterworks-rose.vercel.app/"

    private val cookieJar = JavaNetCookieJar(CookieManager().apply {
        setCookiePolicy(CookiePolicy.ACCEPT_ALL)
    })

    private val loggingInterceptor = HttpLoggingInterceptor().apply {
        level = HttpLoggingInterceptor.Level.BODY
    }

    private val client = OkHttpClient.Builder()
        .cookieJar(cookieJar)
        .addInterceptor(loggingInterceptor)
        .connectTimeout(30, TimeUnit.SECONDS)
        .readTimeout(30, TimeUnit.SECONDS)
        .build()

    val apiService: ApiService by lazy {
        Retrofit.Builder()
            .baseUrl(BASE_URL)
            .client(client)
            .addConverterFactory(GsonConverterFactory.create())
            .build()
            .create(ApiService::class.java)
    }
}
```

### Step 4: Billing Calculator

#### utils/BillingCalculator.kt
```kotlin
object BillingCalculator {

    /**
     * Calculate water bill using tiered rate structure
     *
     * @param consumption Water consumption in cubic meters
     * @param usageType "Residential" or "Commercial"
     * @param rates Current water rates from API
     * @return Calculated bill amount
     */
    fun calculateBill(consumption: Int, usageType: String, rates: WaterRates): Double {
        val tier = if (usageType == "Residential") rates.residential else rates.commercial

        if (consumption <= 0) return 0.0

        var bill = 0.0
        var remaining = consumption

        // Tier 1: 1-5 m³ (Minimum Charge)
        if (remaining > 0) {
            bill += tier.minimum_charge
            remaining -= 5
        }

        // Tier 2: 6-10 m³
        if (remaining > 0) {
            val tier2Amount = minOf(remaining, 5)
            bill += tier2Amount * tier.tier2_rate
            remaining -= tier2Amount
        }

        // Tier 3: 11-20 m³
        if (remaining > 0) {
            val tier3Amount = minOf(remaining, 10)
            bill += tier3Amount * tier.tier3_rate
            remaining -= tier3Amount
        }

        // Tier 4: 21-50 m³
        if (remaining > 0) {
            val tier4Amount = minOf(remaining, 30)
            bill += tier4Amount * tier.tier4_rate
            remaining -= tier4Amount
        }

        // Tier 5: 51+ m³
        if (remaining > 0) {
            bill += remaining * tier.tier5_rate
        }

        return bill
    }

    /**
     * Get detailed billing breakdown for display
     */
    fun getBillingBreakdown(consumption: Int, usageType: String, rates: WaterRates): BillingBreakdown {
        val tier = if (usageType == "Residential") rates.residential else rates.commercial
        val tiers = mutableListOf<TierDetail>()
        var remaining = consumption
        var total = 0.0

        // Tier 1
        if (remaining > 0) {
            tiers.add(TierDetail("Tier 1 (1-5 m³)", 5, tier.minimum_charge, tier.minimum_charge))
            total += tier.minimum_charge
            remaining -= 5
        }

        // Tier 2
        if (remaining > 0) {
            val amount = minOf(remaining, 5)
            val cost = amount * tier.tier2_rate
            tiers.add(TierDetail("Tier 2 (6-10 m³)", amount, tier.tier2_rate, cost))
            total += cost
            remaining -= amount
        }

        // Tier 3
        if (remaining > 0) {
            val amount = minOf(remaining, 10)
            val cost = amount * tier.tier3_rate
            tiers.add(TierDetail("Tier 3 (11-20 m³)", amount, tier.tier3_rate, cost))
            total += cost
            remaining -= amount
        }

        // Tier 4
        if (remaining > 0) {
            val amount = minOf(remaining, 30)
            val cost = amount * tier.tier4_rate
            tiers.add(TierDetail("Tier 4 (21-50 m³)", amount, tier.tier4_rate, cost))
            total += cost
            remaining -= amount
        }

        // Tier 5
        if (remaining > 0) {
            val cost = remaining * tier.tier5_rate
            tiers.add(TierDetail("Tier 5 (51+ m³)", remaining, tier.tier5_rate, cost))
            total += cost
        }

        return BillingBreakdown(tiers, total)
    }
}

data class BillingBreakdown(
    val tiers: List<TierDetail>,
    val total: Double
)

data class TierDetail(
    val tierName: String,
    val cubicMeters: Int,
    val ratePerCubic: Double,
    val subtotal: Double
)
```

### Step 5: Main Activity with Consumer List

#### activities/MainActivity.kt
```kotlin
class MainActivity : AppCompatActivity() {

    private lateinit var recyclerView: RecyclerView
    private lateinit var progressBar: ProgressBar
    private lateinit var consumerAdapter: ConsumerAdapter
    private var waterRates: WaterRates? = null

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)

        setupRecyclerView()
        loadData()
    }

    private fun setupRecyclerView() {
        recyclerView = findViewById(R.id.recyclerViewConsumers)
        progressBar = findViewById(R.id.progressBar)

        recyclerView.layoutManager = LinearLayoutManager(this)
        consumerAdapter = ConsumerAdapter { consumer ->
            onConsumerClicked(consumer)
        }
        recyclerView.adapter = consumerAdapter
    }

    private fun loadData() {
        lifecycleScope.launch {
            try {
                progressBar.visibility = View.VISIBLE

                // Load rates first (cache for the session)
                val ratesResponse = RetrofitClient.apiService.getCurrentRates()
                if (ratesResponse.isSuccessful) {
                    waterRates = ratesResponse.body()
                }

                // Load consumers
                val consumersResponse = RetrofitClient.apiService.getConsumers()
                if (consumersResponse.isSuccessful) {
                    val consumers = consumersResponse.body() ?: emptyList()
                    consumerAdapter.submitList(consumers)
                } else {
                    showError("Failed to load consumers: ${consumersResponse.message()}")
                }

            } catch (e: Exception) {
                showError("Network error: ${e.message}")
            } finally {
                progressBar.visibility = View.GONE
            }
        }
    }

    private fun onConsumerClicked(consumer: Consumer) {
        if (waterRates == null) {
            showError("Please wait, loading rates...")
            return
        }

        // Open meter reading screen
        val intent = Intent(this, MeterReadingActivity::class.java).apply {
            putExtra("CONSUMER", Gson().toJson(consumer))
            putExtra("RATES", Gson().toJson(waterRates))
        }
        startActivity(intent)
    }

    private fun showError(message: String) {
        Toast.makeText(this, message, Toast.LENGTH_LONG).show()
    }
}
```

### Step 6: Meter Reading Screen

#### activities/MeterReadingActivity.kt
```kotlin
class MeterReadingActivity : AppCompatActivity() {

    private lateinit var consumer: Consumer
    private lateinit var rates: WaterRates
    private lateinit var editNewReading: EditText
    private lateinit var textConsumption: TextView
    private lateinit var textEstimatedBill: TextView
    private lateinit var layoutBillingBreakdown: LinearLayout
    private lateinit var buttonSubmit: Button

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_meter_reading)

        // Parse intent data
        consumer = Gson().fromJson(intent.getStringExtra("CONSUMER"), Consumer::class.java)
        rates = Gson().fromJson(intent.getStringExtra("RATES"), WaterRates::class.java)

        setupViews()
        displayConsumerInfo()
    }

    private fun setupViews() {
        findViewById<TextView>(R.id.textConsumerName).text = consumer.name
        findViewById<TextView>(R.id.textAccountNumber).text = consumer.account_number
        findViewById<TextView>(R.id.textUsageType).apply {
            text = consumer.usage_type
            setBackgroundResource(
                if (consumer.usage_type == "Residential")
                    R.drawable.badge_residential
                else
                    R.drawable.badge_commercial
            )
        }
        findViewById<TextView>(R.id.textPreviousReading).text = "${consumer.previous_reading} m³"

        editNewReading = findViewById(R.id.editNewReading)
        textConsumption = findViewById(R.id.textConsumption)
        textEstimatedBill = findViewById(R.id.textEstimatedBill)
        layoutBillingBreakdown = findViewById(R.id.layoutBillingBreakdown)
        buttonSubmit = findViewById(R.id.buttonSubmit)

        // Real-time calculation as user types
        editNewReading.addTextChangedListener { text ->
            calculateBill(text.toString())
        }

        buttonSubmit.setOnClickListener {
            submitReading()
        }
    }

    private fun calculateBill(newReadingStr: String) {
        try {
            val newReading = newReadingStr.toIntOrNull() ?: return

            if (newReading < consumer.previous_reading) {
                textConsumption.text = "Invalid: Reading must be ≥ ${consumer.previous_reading}"
                textConsumption.setTextColor(Color.RED)
                textEstimatedBill.text = "₱0.00"
                buttonSubmit.isEnabled = false
                layoutBillingBreakdown.removeAllViews()
                return
            }

            val consumption = newReading - consumer.previous_reading
            textConsumption.text = "$consumption m³"
            textConsumption.setTextColor(Color.BLACK)

            // Calculate bill
            val breakdown = BillingCalculator.getBillingBreakdown(
                consumption,
                consumer.usage_type,
                rates
            )

            textEstimatedBill.text = "₱${String.format("%.2f", breakdown.total)}"

            // Display breakdown
            displayBillingBreakdown(breakdown)

            buttonSubmit.isEnabled = true

        } catch (e: Exception) {
            Log.e("MeterReading", "Calculation error", e)
        }
    }

    private fun displayBillingBreakdown(breakdown: BillingBreakdown) {
        layoutBillingBreakdown.removeAllViews()

        breakdown.tiers.forEach { tier ->
            val tierView = layoutInflater.inflate(R.layout.item_tier_breakdown, null)
            tierView.findViewById<TextView>(R.id.textTierName).text = tier.tierName
            tierView.findViewById<TextView>(R.id.textTierAmount).text =
                "${tier.cubicMeters} m³ × ₱${tier.ratePerCubic}/m³"
            tierView.findViewById<TextView>(R.id.textTierCost).text =
                "₱${String.format("%.2f", tier.subtotal)}"
            layoutBillingBreakdown.addView(tierView)
        }
    }

    private fun submitReading() {
        val newReading = editNewReading.text.toString().toIntOrNull() ?: return

        if (newReading < consumer.previous_reading) {
            Toast.makeText(this, "Invalid reading value", Toast.LENGTH_SHORT).show()
            return
        }

        // Show confirmation dialog
        val consumption = newReading - consumer.previous_reading
        val estimatedBill = BillingCalculator.calculateBill(consumption, consumer.usage_type, rates)

        AlertDialog.Builder(this)
            .setTitle("Confirm Submission")
            .setMessage("""
                Consumer: ${consumer.name}
                Previous Reading: ${consumer.previous_reading} m³
                New Reading: $newReading m³
                Consumption: $consumption m³
                Estimated Bill: ₱${String.format("%.2f", estimatedBill)}

                Submit this reading?
            """.trimIndent())
            .setPositiveButton("Submit") { _, _ ->
                performSubmission(newReading)
            }
            .setNegativeButton("Cancel", null)
            .show()
    }

    private fun performSubmission(readingValue: Int) {
        lifecycleScope.launch {
            try {
                buttonSubmit.isEnabled = false

                val submission = ReadingSubmission(
                    consumer_id = consumer.id,
                    reading_value = readingValue,
                    reading_date = SimpleDateFormat("yyyy-MM-dd", Locale.getDefault())
                        .format(Date()),
                    source = "mobile_app"
                )

                val response = RetrofitClient.apiService.submitReading(submission)

                if (response.isSuccessful) {
                    val result = response.body()
                    Toast.makeText(
                        this@MeterReadingActivity,
                        "Reading submitted! OR#${result?.reading_id}",
                        Toast.LENGTH_LONG
                    ).show()
                    finish()
                } else {
                    val errorBody = response.errorBody()?.string()
                    Toast.makeText(
                        this@MeterReadingActivity,
                        "Error: $errorBody",
                        Toast.LENGTH_LONG
                    ).show()
                }

            } catch (e: Exception) {
                Toast.makeText(
                    this@MeterReadingActivity,
                    "Network error: ${e.message}",
                    Toast.LENGTH_LONG
                ).show()
            } finally {
                buttonSubmit.isEnabled = true
            }
        }
    }
}
```

---

## IoT Smart Meter Integration

### Arduino/ESP32 Code Example

```cpp
#include <WiFi.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>

// WiFi credentials
const char* ssid = "YOUR_WIFI_SSID";
const char* password = "YOUR_WIFI_PASSWORD";

// API Configuration
const char* apiUrl = "https://waterworks-rose.vercel.app";
const char* username = "smart_meter_user";
const char* userPassword = "your_password";

// Meter configuration
const int CONSUMER_ID = 1;  // Set for each meter
const int PULSE_PIN = 2;     // Water meter pulse output
const float LITERS_PER_PULSE = 1.0;  // Calibration value

// State
volatile int pulseCount = 0;
String sessionCookie = "";
int currentReading = 0;

void setup() {
  Serial.begin(115200);
  pinMode(PULSE_PIN, INPUT_PULLUP);
  attachInterrupt(digitalPinToInterrupt(PULSE_PIN), pulseCounter, FALLING);

  // Connect to WiFi
  WiFi.begin(ssid, password);
  Serial.print("Connecting to WiFi");
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println("\nWiFi connected!");
  Serial.println(WiFi.localIP());

  // Login to API
  if (loginToAPI()) {
    Serial.println("Successfully logged in to waterworks API");

    // Get previous reading
    getPreviousReading();
  }
}

void loop() {
  // Check if we've accumulated enough pulses (e.g., every 10 liters)
  if (pulseCount >= 10) {
    currentReading += pulseCount;
    Serial.printf("Current reading: %d m³\n", currentReading / 1000);
    pulseCount = 0;
  }

  // Submit reading every hour (or on schedule)
  static unsigned long lastSubmit = 0;
  if (millis() - lastSubmit > 3600000) {  // 1 hour
    submitReading();
    lastSubmit = millis();
  }

  delay(100);
}

void IRAM_ATTR pulseCounter() {
  pulseCount++;
}

bool loginToAPI() {
  HTTPClient http;
  http.begin(String(apiUrl) + "/api/login/");
  http.addHeader("Content-Type", "application/json");

  StaticJsonDocument<200> doc;
  doc["username"] = username;
  doc["password"] = userPassword;

  String requestBody;
  serializeJson(doc, requestBody);

  int httpCode = http.POST(requestBody);

  if (httpCode == 200) {
    // Extract session cookie
    String cookie = http.header("Set-Cookie");
    if (cookie.length() > 0) {
      sessionCookie = cookie.substring(0, cookie.indexOf(';'));
      http.end();
      return true;
    }
  }

  http.end();
  return false;
}

void getPreviousReading() {
  HTTPClient http;
  http.begin(String(apiUrl) + "/api/consumers/" + String(CONSUMER_ID) + "/previous-reading/");
  http.addHeader("Cookie", sessionCookie);

  int httpCode = http.GET();

  if (httpCode == 200) {
    String payload = http.getString();

    StaticJsonDocument<512> doc;
    deserializeJson(doc, payload);

    currentReading = doc["previous_reading"];
    Serial.printf("Previous reading loaded: %d m³\n", currentReading);
  }

  http.end();
}

void submitReading() {
  HTTPClient http;
  http.begin(String(apiUrl) + "/api/meter-readings/");
  http.addHeader("Content-Type", "application/json");
  http.addHeader("Cookie", sessionCookie);

  // Get current date
  time_t now = time(nullptr);
  struct tm* timeinfo = localtime(&now);
  char dateStr[11];
  strftime(dateStr, sizeof(dateStr), "%Y-%m-%d", timeinfo);

  StaticJsonDocument<300> doc;
  doc["consumer_id"] = CONSUMER_ID;
  doc["reading_value"] = currentReading / 1000;  // Convert to m³
  doc["reading_date"] = dateStr;
  doc["source"] = "smart_meter";

  String requestBody;
  serializeJson(doc, requestBody);

  Serial.println("Submitting reading: " + requestBody);

  int httpCode = http.POST(requestBody);

  if (httpCode == 201 || httpCode == 200) {
    String response = http.getString();
    Serial.println("Reading submitted successfully!");
    Serial.println(response);
  } else {
    Serial.printf("Failed to submit reading. HTTP code: %d\n", httpCode);
    Serial.println(http.getString());
  }

  http.end();
}
```

---

## Testing Guide

### 1. Test Authentication
```bash
curl -X POST https://waterworks-rose.vercel.app/api/login/ \
  -H "Content-Type: application/json" \
  -d '{"username":"test_user","password":"test_pass"}' \
  -c cookies.txt
```

### 2. Test Get Consumers
```bash
curl https://waterworks-rose.vercel.app/api/consumers/ \
  -b cookies.txt
```

**Expected Response**:
```json
[
  {
    "id": 1,
    "usage_type": "Residential",  ← Check this field exists!
    "previous_reading": 1250,
    ...
  }
]
```

### 3. Test Get Rates
```bash
curl https://waterworks-rose.vercel.app/api/rates/ \
  -b cookies.txt
```

### 4. Test Submit Reading
```bash
curl -X POST https://waterworks-rose.vercel.app/api/meter-readings/ \
  -H "Content-Type: application/json" \
  -b cookies.txt \
  -d '{
    "consumer_id": 1,
    "reading_value": 1273,
    "reading_date": "2024-11-27",
    "source": "mobile_app"
  }'
```

---

## Deployment Checklist

### Android App
- [ ] Update BASE_URL to production
- [ ] Add network security config (allow cleartext for local testing only)
- [ ] Implement proper error handling
- [ ] Add offline mode (cache readings, sync later)
- [ ] Test on different Android versions
- [ ] Add ProGuard rules for release build

### IoT Smart Meter
- [ ] Calibrate LITERS_PER_PULSE for your water meter
- [ ] Set unique CONSUMER_ID for each device
- [ ] Implement NTP time sync for accurate timestamps
- [ ] Add failover/retry logic for network errors
- [ ] Store unsent readings in EEPROM/SPIFFS
- [ ] Add OTA update capability
- [ ] Implement watchdog timer for auto-recovery

---

## Support

For issues or questions:
1. Check API documentation: `docs/ANDROID_API_GUIDE.md`
2. Review system logs in admin dashboard
3. Contact system administrator

---

## License

This guide is part of the Balilihan Waterworks Management System.
