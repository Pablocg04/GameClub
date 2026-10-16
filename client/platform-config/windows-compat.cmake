# webview_windows 0.4.0 uses the experimental coroutine ABI. MSVC 14.51 still
# supports that ABI but requires this specific opt-in for its deprecation guard.
if(MSVC AND TARGET webview_windows_plugin)
  target_compile_definitions(webview_windows_plugin PRIVATE
    _SILENCE_EXPERIMENTAL_COROUTINE_DEPRECATION_WARNINGS)
endif()
