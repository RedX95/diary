import 'dart:async';
import 'dart:convert';

import 'package:flet/flet.dart';
import 'package:speech_to_text/speech_to_text.dart';
import 'package:speech_to_text/speech_recognition_error.dart';
import 'package:speech_to_text/speech_recognition_result.dart';

class SttService extends FletService {
  SttService({required super.control});

  final SpeechToText _speech = SpeechToText();
  bool _initialized = false;
  Timer? _cloudTimer;

  @override
  void init() {
    super.init();
    control.addInvokeMethodListener(_onMethod);
  }

  @override
  void dispose() {
    control.removeInvokeMethodListener(_onMethod);
    _cancelCloudTimer();
    if (_initialized) {
      _speech.cancel();
    }
    super.dispose();
  }

  void _cancelCloudTimer() {
    _cloudTimer?.cancel();
    _cloudTimer = null;
  }

  void _onCloudTimeout() {
    _cloudTimer = null;
    control.triggerEvent("error", jsonEncode({
      "error": "cloud_recognition_timeout",
      "permanent": false,
    }));
    _speech.cancel();
  }

  void _onError(SpeechRecognitionError error) {
    _cancelCloudTimer();
    control.triggerEvent("error", jsonEncode({
      "error": error.errorMsg,
      "permanent": error.permanent,
    }));
  }

  void _onStatus(String status) {
    control.triggerEvent("status", jsonEncode({
      "status": status,
    }));
  }

  void _onResult(SpeechRecognitionResult result) {
    _cancelCloudTimer();
    control.triggerEvent("result", jsonEncode({
      "text": result.recognizedWords,
      "final": result.finalResult,
      "confidence": result.confidence,
      "alternates": result.alternates.map((a) => {
        "text": a.recognizedWords,
        "confidence": a.confidence,
      }).toList(),
    }));
  }

  void _onSoundLevel(double level) {
    control.triggerEvent("sound_level", jsonEncode({
      "level": level,
    }));
  }

  ListenMode _parseListenMode(String value) {
    switch (value) {
      case "dictation":
        return ListenMode.dictation;
      case "search":
        return ListenMode.search;
      case "confirmation":
        return ListenMode.confirmation;
      default:
        return ListenMode.confirmation;
    }
  }

  Future<dynamic> _onMethod(String name, dynamic args) async {
    try {
      switch (name) {
        case "initialize":
          final available = await _speech.initialize(
            onError: _onError,
            onStatus: _onStatus,
          );
          _initialized = available;
          return available.toString();

        case "listen":
          if (!_initialized) {
            return "error:not initialized — call initialize() first";
          }
          final a = Map<String, dynamic>.from(args as Map);
          final localeId = a["locale_id"] as String? ?? "";
          final listenForSeconds = a["listen_for_seconds"] as int? ?? 0;
          final pauseForSeconds = a["pause_for_seconds"] as int? ?? 0;
          final partialResults = a["partial_results"] as bool? ?? true;
          final onDevice = a["on_device"] as bool? ?? false;
          final cancelOnError = a["cancel_on_error"] as bool? ?? false;
          final sampleRate = a["sample_rate"] as int? ?? 0;
          final listenMode = _parseListenMode(
              a["listen_mode"] as String? ?? "confirmation");

          final autoPunctuation = a["auto_punctuation"] as bool? ?? false;
          final enableHapticFeedback = a["enable_haptic_feedback"] as bool? ?? false;
          final cloudTimeoutSeconds = a["cloud_timeout_seconds"] as int? ?? 15;

          await _speech.listen(
            onResult: _onResult,
            onSoundLevelChange: _onSoundLevel,
            localeId: localeId.isNotEmpty ? localeId : null,
            listenFor: listenForSeconds > 0
                ? Duration(seconds: listenForSeconds)
                : null,
            pauseFor: pauseForSeconds > 0
                ? Duration(seconds: pauseForSeconds)
                : null,
            listenOptions: SpeechListenOptions(
              partialResults: partialResults,
              onDevice: onDevice,
              cancelOnError: cancelOnError,
              sampleRate: sampleRate > 0 ? sampleRate : 0,
              listenMode: listenMode,
              autoPunctuation: autoPunctuation,
              enableHapticFeedback: enableHapticFeedback,
            ),
          );
          _cancelCloudTimer();
          if (!onDevice && cloudTimeoutSeconds > 0) {
            _cloudTimer = Timer(
              Duration(seconds: cloudTimeoutSeconds),
              _onCloudTimeout,
            );
          }
          return "ok";

        case "stop":
          _cancelCloudTimer();
          await _speech.stop();
          return "ok";

        case "cancel":
          _cancelCloudTimer();
          await _speech.cancel();
          return "ok";

        case "change_pause_for":
          if (!_initialized) {
            return "error:not initialized — call initialize() first";
          }
          final seconds = args as int;
          try {
            _speech.changePauseFor(Duration(seconds: seconds));
          } on ListenNotStartedException {
            return "error:not listening — call listen() before change_pause_for()";
          }
          return "ok";

        case "locales":
          if (!_initialized) {
            return "error:not initialized — call initialize() first";
          }
          final locales = await _speech.locales();
          final list = locales.map((l) =>
            {"id": l.localeId, "name": l.name}
          ).toList();
          return jsonEncode(list);

        case "system_locale":
          if (!_initialized) {
            return "error:not initialized — call initialize() first";
          }
          final locale = await _speech.systemLocale();
          if (locale == null) {
            return jsonEncode({"id": "", "name": ""});
          }
          return jsonEncode({"id": locale.localeId, "name": locale.name});

        case "is_listening":
          return _speech.isListening.toString();

        case "has_permission":
          return (await _speech.hasPermission).toString();
      }
      return null;
    } catch (e) {
      return "error:$e";
    }
  }
}
