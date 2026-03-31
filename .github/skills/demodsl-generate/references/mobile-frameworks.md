# Mobile App Frameworks — DemoDSL Integration Guide

How to configure DemoDSL mobile demos for each app framework.
When generating a mobile demo YAML, detect the user's framework and apply the corresponding setup below.

## Framework Detection

| Marker file / dependency | Framework |
|--------------------------|-----------|
| `app.json` + `expo` in dependencies | **Expo (React Native)** |
| `react-native.config.js` or `android/` + `ios/` + `react-native` dep | **React Native CLI** |
| `pubspec.yaml` + `flutter` dep | **Flutter** |
| `capacitor.config.ts` or `capacitor.config.json` | **Capacitor (Ionic)** |
| `config.xml` + `cordova` dep | **Cordova** |
| `src/main/kotlin/**` or `src/main/java/**` + `build.gradle.kts` | **Native Android (Kotlin/Java)** |
| `*.xcodeproj` or `*.xcworkspace` + `*.swift` or `*.m` | **Native iOS (Swift/ObjC)** |
| `.NET MAUI` or `*.csproj` with `Microsoft.Maui` | **.NET MAUI** |
| `NativeScript` in `package.json` | **NativeScript** |

---

## Expo (React Native)

### Modes

| Mode | Quand l'utiliser | `mobile:` config |
|------|------------------|------------------|
| **Expo Go** | Prototypage, pas de modules natifs custom | `app_package: "host.exp.exponent"` (Android) / `bundle_id: "host.exp.Exponent"` (iOS) |
| **Dev Build (EAS)** | Modules natifs custom | Lire `app.json` → `android.package` / `ios.bundleIdentifier` |
| **APK/IPA buildé** | CI, démo offline | `app: "./build/myapp.apk"` ou `app: "./build/myapp.ipa"` |

### Locators

Expo/React Native rend les composants en vues natives. Utiliser :
- `accessibilityLabel` → locator `{ type: "accessibility_id", value: "..." }` (cross-platform)
- `testID` → fonctionne comme `accessibility_id` sur iOS, comme `id` sur Android

```tsx
// Dans le code source de l'app
<Pressable accessibilityLabel="login-button" onPress={handleLogin}>
  <Text>Se connecter</Text>
</Pressable>
<TextInput accessibilityLabel="email-input" placeholder="Email" />
```

### Config Android
```yaml
mobile:
  platform: "android"
  device_name: "emulator-5554"       # ou nom d'émulateur AVD
  app_package: "host.exp.exponent"    # Expo Go
  # Pour dev build : lire app.json → expo.android.package
  # Pour APK : app: "./android/app/build/outputs/apk/release/app-release.apk"
  app_activity: "host.exp.exponent.experience.HomeActivity"
  automation_name: "UiAutomator2"     # Required for Android
```

### Config iOS
```yaml
mobile:
  platform: "ios"
  device_name: "iPhone 15 Pro"
  bundle_id: "host.exp.Exponent"      # Expo Go
  # Pour dev build : lire app.json → expo.ios.bundleIdentifier
  # Pour .app : app: "./ios/build/Build/Products/Release-iphonesimulator/MyApp.app"
  automation_name: "XCUITest"           # Required for iOS
```

### ⚠️ iOS/Expo : problèmes de locators

Sur iOS avec Expo/React Native, `accessibility_id` peut ne pas fonctionner même si `accessibilityLabel` est défini dans le code. Cela arrive quand :
- L'app utilise `accessibilityLabel` au lieu de `accessibilityIdentifier` (XCUITest ne voit que `accessibilityIdentifier`)
- L'app n'a pas été buildée avec les bons flags d'accessibilité

**Ordre de fallback recommandé** : `accessibility_id` → `ios_predicate` → `ios_class_chain` → coordonnées

💡 **Tip** : utilisez `demodsl inspect <config>` pour dumper l'arbre d'accessibilité et trouver les bons locators. Ajoutez `--raw` pour le XML brut.

```yaml
# Quand accessibility_id échoue, utiliser ios_predicate :
- action: "tap"
  locator: { type: "ios_predicate", value: "name == 'Login'" }

# Ou les coordonnées en dernier recours :
- action: "tap"
  x: 197
  y: 310
  narration: "Tap sur le bouton"
```

### Auto-détection du simulateur iOS
Sur macOS, DemoDSL peut auto-détecter un simulateur iOS booté via `xcrun simctl`. Le module `demodsl.providers.ios_detect` fournit `detect_booted_simulator()` qui retourne `{'device_name': '…', 'udid': '…'}` ou `None`.

### Expo Go — pre_steps pour naviguer jusqu'à l'app
```yaml
pre_steps:
  - action: "wait_for"
    locator: { type: "text", value: "Projects" }
    timeout: 15
  - action: "tap"
    locator: { type: "text", value: "mon-app" }
  - action: "wait_for"
    locator: { type: "accessibility_id", value: "app-loaded" }
    timeout: 20
```

### Recommandation
Préférer un **dev build** (`npx expo run:android` / `npx expo run:ios`) — l'app se lance directement sans passer par Expo Go.

---

## React Native CLI (bare)

### Package & Activity

- **Android** : lire `android/app/build.gradle` → `applicationId` (ex: `"com.myapp"`)
- **iOS** : lire le `.xcodeproj/project.pbxproj` → `PRODUCT_BUNDLE_IDENTIFIER`, ou `ios/MyApp/Info.plist` → `CFBundleIdentifier`
- **Activity** : généralement `com.myapp.MainActivity`

### Locators

Identique à Expo : `accessibilityLabel` → `accessibility_id`.

```tsx
<TouchableOpacity accessibilityLabel="submit-btn">
  <Text>Submit</Text>
</TouchableOpacity>
```

### Config Android
```yaml
mobile:
  platform: "android"
  device_name: "emulator-5554"
  app: "./android/app/build/outputs/apk/debug/app-debug.apk"
  # OU si l'app est déjà installée :
  app_package: "com.myapp"
  app_activity: "com.myapp.MainActivity"
```

### Config iOS
```yaml
mobile:
  platform: "ios"
  device_name: "iPhone 15 Pro"
  app: "./ios/build/Build/Products/Debug-iphonesimulator/MyApp.app"
  # OU si l'app est déjà installée :
  bundle_id: "com.myapp"
```

---

## Flutter

### Package & Activity

- **Android** : lire `android/app/build.gradle` → `applicationId` (ex: `"com.example.myapp"`)
- **Activity** : `com.example.myapp.MainActivity` (par défaut Flutter)
- **iOS** : lire `ios/Runner.xcodeproj/project.pbxproj` → `PRODUCT_BUNDLE_IDENTIFIER`

### Locators

Flutter utilise Semantics widgets. Appium accède aux éléments via :
- `Semantics(label: "login")` → locator `{ type: "accessibility_id", value: "login" }` (cross-platform)
- `Key("my-key")` → locator `{ type: "id", value: "my-key" }` (Android via UiAutomator2)
- Pour iOS, préférer `accessibility_id` via `Semantics`

```dart
// Dans le code source Flutter
ElevatedButton(
  key: const Key("submit-btn"),
  child: Semantics(
    label: "submit-button",
    child: const Text("Submit"),
  ),
  onPressed: () {},
)
```

### Config Android
```yaml
mobile:
  platform: "android"
  device_name: "emulator-5554"
  app: "./build/app/outputs/flutter-apk/app-debug.apk"
  # OU :
  app_package: "com.example.myapp"
  app_activity: "com.example.myapp.MainActivity"
```

### Config iOS
```yaml
mobile:
  platform: "ios"
  device_name: "iPhone 15 Pro"
  app: "./build/ios/iphonesimulator/Runner.app"
  # OU :
  bundle_id: "com.example.myapp"
```

### Notes
- Installer le driver Flutter pour Appium : `appium driver install appium-flutter-driver` pour un accès direct aux widgets Flutter (optionnel, les locators natifs suffisent pour les démos)
- Les animations Flutter sont fluides — utiliser `wait` suffisant pour laisser les transitions se terminer

---

## Capacitor (Ionic)

### Package & Activity

- **Android** : lire `capacitor.config.ts` → `appId` (ex: `"com.mycompany.myapp"`)
- **Activity** : `com.mycompany.myapp.MainActivity`
- **iOS** : même `appId` comme `bundleIdentifier`

### Locators

Capacitor emballe une WebView. Deux modes :
1. **Contexte natif** : locators natifs pour la navigation système (splash, permissions)
2. **Contexte WebView** : Appium peut switcher vers le contexte WebView et utiliser des locators CSS/XPath web

Pour les démos, rester en **contexte natif** avec `accessibility_id` est plus simple :
```html
<!-- Dans le code source Ionic/Angular/React/Vue -->
<ion-button aria-label="login-button" (click)="login()">Login</ion-button>
<ion-input aria-label="email-input" placeholder="Email"></ion-input>
```

### Config Android
```yaml
mobile:
  platform: "android"
  device_name: "emulator-5554"
  app: "./android/app/build/outputs/apk/debug/app-debug.apk"
  app_package: "com.mycompany.myapp"
  app_activity: "com.mycompany.myapp.MainActivity"
```

### Config iOS
```yaml
mobile:
  platform: "ios"
  device_name: "iPhone 15 Pro"
  app: "./ios/App/build/Debug-iphonesimulator/App.app"
  bundle_id: "com.mycompany.myapp"
```

---

## Cordova

### Package & Activity

- **Android** : lire `config.xml` → `<widget id="com.myapp.app">`
- **Activity** : `com.myapp.app.MainActivity`
- **iOS** : même `id` dans `config.xml`

### Locators

Même approche que Capacitor (WebView) — utiliser `aria-label` dans le HTML :
```html
<button aria-label="start-demo">Start</button>
```

### Config Android
```yaml
mobile:
  platform: "android"
  device_name: "emulator-5554"
  app: "./platforms/android/app/build/outputs/apk/debug/app-debug.apk"
  app_package: "com.myapp.app"
  app_activity: "com.myapp.app.MainActivity"
```

### Config iOS
```yaml
mobile:
  platform: "ios"
  device_name: "iPhone 15 Pro"
  app: "./platforms/ios/build/emulator/MyApp.app"
  bundle_id: "com.myapp.app"
```

---

## Native Android (Kotlin / Java)

### Package & Activity

- Lire `app/build.gradle.kts` → `applicationId` (ex: `"com.example.myapp"`)
- Activity de lancement : lire `AndroidManifest.xml` → `<activity>` avec `<intent-filter>` contenant `MAIN` + `LAUNCHER`

### Locators

Android natif supporte tous les locators :
- `android:contentDescription="..."` → `{ type: "accessibility_id", value: "..." }`
- `android:id="@+id/btn_login"` → `{ type: "id", value: "com.example.myapp:id/btn_login" }`
- UiAutomator2 : `{ type: "android_uiautomator", value: "new UiSelector().text(\"Login\")" }`

```kotlin
// Dans le code source Android
Button(onClick = { /* ... */ },
    modifier = Modifier.semantics { contentDescription = "login-button" }
) { Text("Login") }

// XML layout
<Button
    android:id="@+id/btn_login"
    android:contentDescription="login-button"
    android:text="Login" />
```

### Config
```yaml
mobile:
  platform: "android"
  device_name: "emulator-5554"
  app: "./app/build/outputs/apk/debug/app-debug.apk"
  app_package: "com.example.myapp"
  app_activity: "com.example.myapp.MainActivity"
  automation_name: "UiAutomator2"
```

---

## Native iOS (Swift / Objective-C)

### Bundle ID

- Lire `*.xcodeproj/project.pbxproj` → `PRODUCT_BUNDLE_IDENTIFIER`
- Ou dans Xcode : target → General → Bundle Identifier

### Locators

iOS natif supporte :
- `accessibilityIdentifier` → `{ type: "accessibility_id", value: "..." }`
- iOS Predicate : `{ type: "ios_predicate", value: "name == 'login-button'" }`
- iOS Class Chain : `{ type: "ios_class_chain", value: "**/XCUIElementTypeButton[`name == 'Login'`]" }`

```swift
// SwiftUI
Button("Login") { /* ... */ }
    .accessibilityIdentifier("login-button")

// UIKit
loginButton.accessibilityIdentifier = "login-button"
```

### Config
```yaml
mobile:
  platform: "ios"
  device_name: "iPhone 15 Pro"
  app: "./build/Debug-iphonesimulator/MyApp.app"
  bundle_id: "com.example.myapp"
  automation_name: "XCUITest"
```

---

## .NET MAUI

### Package & Activity

- **Android** : lire `Platforms/Android/AndroidManifest.xml` → `package` attribute, ou `.csproj` → `<ApplicationId>`
- **Activity** : `crc64xxxxxxxxxxxx.MainActivity` (MAUI génère un hash — utiliser `app` plutôt que `app_package`)
- **iOS** : lire `.csproj` → `<ApplicationId>` ou `Info.plist` → `CFBundleIdentifier`

### Locators

MAUI supporte `AutomationId` → `accessibility_id` :
```xml
<Button AutomationId="login-button" Text="Login" Clicked="OnLoginClicked" />
<Entry AutomationId="email-input" Placeholder="Email" />
```

### Config Android
```yaml
mobile:
  platform: "android"
  device_name: "emulator-5554"
  app: "./bin/Debug/net8.0-android/com.example.myapp-Signed.apk"
```

### Config iOS
```yaml
mobile:
  platform: "ios"
  device_name: "iPhone 15 Pro"
  app: "./bin/Debug/net8.0-ios/iossimulator-x64/MyApp.app"
  bundle_id: "com.example.myapp"
```

---

## NativeScript

### Package & Activity

- **Android** : lire `nativescript.config.ts` → `id` (ex: `"org.nativescript.myapp"`)
- **Activity** : `com.tns.NativeScriptActivity`
- **iOS** : même `id`

### Locators

NativeScript : `automationText` → `accessibility_id` :
```xml
<Button automationText="login-button" text="Login" tap="onLogin" />
```
Ou en Angular/Vue :
```html
<Button automationText="login-button" text="Login" (tap)="onLogin()"></Button>
```

### Config Android
```yaml
mobile:
  platform: "android"
  device_name: "emulator-5554"
  app: "./platforms/android/app/build/outputs/apk/debug/app-debug.apk"
  app_package: "org.nativescript.myapp"
  app_activity: "com.tns.NativeScriptActivity"
```

### Config iOS
```yaml
mobile:
  platform: "ios"
  device_name: "iPhone 15 Pro"
  app: "./platforms/ios/build/Debug-iphonesimulator/MyApp.app"
  bundle_id: "org.nativescript.myapp"
```

---

## Cross-Framework Locator Summary

| Framework | Prop source code | Locator DemoDSL | Plateforme |
|-----------|-----------------|-----------------|------------|
| Expo / React Native | `accessibilityLabel` | `{ type: "accessibility_id" }` | Android + iOS |
| Flutter | `Semantics(label: "...")` | `{ type: "accessibility_id" }` | Android + iOS |
| Capacitor / Cordova | `aria-label` | `{ type: "accessibility_id" }` | Android + iOS |
| Android natif | `contentDescription` | `{ type: "accessibility_id" }` | Android |
| Android natif | `android:id` | `{ type: "id", value: "pkg:id/name" }` | Android |
| iOS natif | `accessibilityIdentifier` | `{ type: "accessibility_id" }` | iOS |
| .NET MAUI | `AutomationId` | `{ type: "accessibility_id" }` | Android + iOS |
| NativeScript | `automationText` | `{ type: "accessibility_id" }` | Android + iOS |

**Règle universelle** : `accessibility_id` fonctionne partout *quand l'app a été configurée pour*. C'est le locator par défaut pour les démos mobiles.

> **⚠️ Note iOS/Expo** : Si `accessibility_id` ne fonctionne pas, essayez dans l'ordre : `ios_predicate` → `ios_class_chain` → coordonnées (`x`/`y`). Voir la section "Expo > iOS" ci-dessus.

### Tap par coordonnées (fallback universel)

Quand aucun locator ne fonctionne, utiliser les coordonnées :
```yaml
# x/y sont des alias de start_x/start_y pour le tap
- action: "tap"
  x: 197
  y: 310
  narration: "Tap par coordonnées"

# Forme longue (identique)
- action: "tap"
  start_x: 197
  start_y: 310
```

## Appium Setup Reminder

```bash
# Requis avant tout
npm install -g appium
appium driver install uiautomator2   # Android
appium driver install xcuitest       # iOS

# Démarrer le serveur
appium --port 4723

# Vérifier
appium driver list --installed
```

## Common Actions Available

All mobile actions: `tap`, `swipe`, `pinch`, `long_press`, `type`, `scroll`, `back`, `home`, `notification`, `app_switch`, `rotate_device`, `shake`, `wait_for`, `screenshot`.
