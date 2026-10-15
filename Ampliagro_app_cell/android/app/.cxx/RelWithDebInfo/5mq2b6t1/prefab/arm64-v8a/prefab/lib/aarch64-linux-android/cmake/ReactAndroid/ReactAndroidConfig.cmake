if(NOT TARGET ReactAndroid::hermestooling)
add_library(ReactAndroid::hermestooling SHARED IMPORTED)
set_target_properties(ReactAndroid::hermestooling PROPERTIES
    IMPORTED_LOCATION "C:/Users/lucas/.gradle/caches/9.4.1/transforms/83daf106ead88e7e3c5ea19248e78529/transformed/react-android-0.87.1-release/prefab/modules/hermestooling/libs/android.arm64-v8a/libhermestooling.so"
    INTERFACE_INCLUDE_DIRECTORIES "C:/Users/lucas/.gradle/caches/9.4.1/transforms/83daf106ead88e7e3c5ea19248e78529/transformed/react-android-0.87.1-release/prefab/modules/hermestooling/include"
    INTERFACE_LINK_LIBRARIES ""
)
endif()

if(NOT TARGET ReactAndroid::jsi)
add_library(ReactAndroid::jsi SHARED IMPORTED)
set_target_properties(ReactAndroid::jsi PROPERTIES
    IMPORTED_LOCATION "C:/Users/lucas/.gradle/caches/9.4.1/transforms/83daf106ead88e7e3c5ea19248e78529/transformed/react-android-0.87.1-release/prefab/modules/jsi/libs/android.arm64-v8a/libjsi.so"
    INTERFACE_INCLUDE_DIRECTORIES "C:/Users/lucas/.gradle/caches/9.4.1/transforms/83daf106ead88e7e3c5ea19248e78529/transformed/react-android-0.87.1-release/prefab/modules/jsi/include"
    INTERFACE_LINK_LIBRARIES ""
)
endif()

if(NOT TARGET ReactAndroid::reactnative)
add_library(ReactAndroid::reactnative SHARED IMPORTED)
set_target_properties(ReactAndroid::reactnative PROPERTIES
    IMPORTED_LOCATION "C:/Users/lucas/.gradle/caches/9.4.1/transforms/83daf106ead88e7e3c5ea19248e78529/transformed/react-android-0.87.1-release/prefab/modules/reactnative/libs/android.arm64-v8a/libreactnative.so"
    INTERFACE_INCLUDE_DIRECTORIES "C:/Users/lucas/.gradle/caches/9.4.1/transforms/83daf106ead88e7e3c5ea19248e78529/transformed/react-android-0.87.1-release/prefab/modules/reactnative/include"
    INTERFACE_LINK_LIBRARIES ""
)
endif()

