import 'dart:async';

import 'package:flet/flet.dart';
import 'package:flutter/services.dart';

class ContactLauncherService extends FletService {
  ContactLauncherService({required super.control});

  static const MethodChannel _channel =
      MethodChannel("flet_contact_launcher/native");
  String _lastRequestId = "";

  @override
  void init() {
    super.init();
  }

  @override
  void update() {
    super.update();

    final requestId = control.get<String>("request_id", "") ?? "";
    final phone = control.get<String>("phone_to_open", "") ?? "";
    if (requestId.isEmpty || requestId == _lastRequestId || phone.isEmpty) {
      return;
    }

    _lastRequestId = requestId;
    unawaited(_openContact(requestId, phone));
  }

  Future<void> _openContact(String requestId, String phone) async {
    String status;
    try {
      status = await _channel
              .invokeMethod<String>("openContact", {"phone": phone})
              .timeout(
                const Duration(seconds: 6),
                onTimeout: () => "error:channel_timeout",
              ) ??
          "no_result";
    } catch (e) {
      status = "error:$e";
    }

    control.triggerEvent("status", {
      "status": status,
      "request_id": requestId,
      "phone": phone,
    });
  }
}
