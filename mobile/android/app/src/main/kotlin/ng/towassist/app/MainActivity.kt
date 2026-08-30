package ng.towassist.app

import android.app.NotificationChannel
import android.app.NotificationManager
import android.os.Build
import android.os.Bundle
import io.flutter.embedding.android.FlutterActivity

class MainActivity : FlutterActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        createJobNotificationChannel()
    }

    /**
     * The channel the backend targets when sending job updates.
     *
     * Android requires the app to create a channel before anything can post
     * to it. Without this, FCM logs "Notification Channel requested
     * (towassist_jobs) has not been created" and falls back to a generic
     * channel the user cannot tune separately - so someone who mutes
     * marketing would also mute "your driver has arrived".
     */
    private fun createJobNotificationChannel() {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.O) return
        val channel = NotificationChannel(
            "towassist_jobs",
            "Job updates",
            NotificationManager.IMPORTANCE_HIGH,
        ).apply {
            description = "Dispatch, arrival and completion updates for your requests"
        }
        val manager = getSystemService(NotificationManager::class.java)
        manager?.createNotificationChannel(channel)
    }
}
