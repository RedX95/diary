import 'package:flet/flet.dart';

import 'stt_service.dart';

class Extension extends FletExtension {
  @override
  FletService? createService(Control control) {
    switch (control.type) {
      case "flet_stt":
        return SttService(control: control);
      default:
        return null;
    }
  }
}
