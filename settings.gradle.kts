pluginManagement {
    repositories {
        google()
        mavenCentral()
        gradlePluginPortal()
    }
}

dependencyResolutionManagement {
    repositoriesMode.set(RepositoriesMode.FAIL_ON_PROJECT_REPOS)
    repositories {
        google()
        mavenCentral()
    }
}

rootProject.name = "auto-test"

include(":agent-protocol")
include(":agent-core")
include(":agent-accessibility")
include(":agent-root")
include(":agent-performance")
include(":agent-transport")
include(":agent-app")
