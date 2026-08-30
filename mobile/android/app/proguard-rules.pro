# Flutter's engine is reached reflectively from native code; R8 cannot see those
# entry points and would strip them, producing an APK that installs and then
# crashes on launch.
-keep class io.flutter.** { *; }
-keep class io.flutter.plugins.** { *; }

# Firebase Messaging resolves its service and receivers from the manifest by
# name, so they must survive obfuscation or push silently stops arriving.
-keep class com.google.firebase.** { *; }
-dontwarn com.google.firebase.**

# Flutter's engine references Play Core's deferred-component and split-install
# APIs, but this app does not use deferred components and does not depend on
# Play Core - so R8 sees the references and fails on classes that will never be
# reached at runtime. Silence them rather than pulling in an unused library.
-dontwarn com.google.android.play.core.**
-keep class io.flutter.embedding.engine.deferredcomponents.** { *; }
