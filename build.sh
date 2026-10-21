cd ~/Workspace/SigmaStreams/Silo/source/silo-android

export JAVA_HOME=/usr/lib/jvm/java-21-openjdk-amd64
export ANDROID_HOME="$HOME/Android"
export PATH="$JAVA_HOME/bin:$ANDROID_HOME/cmdline-tools/latest/bin:$ANDROID_HOME/Sdk/platform-tools:$PATH"

# Phone
./gradlew :androidApp:assembleRelease -PallowDebugReleaseSigning=true

# TV
./gradlew :androidTvApp:assembleRelease -PallowDebugReleaseSigning=true