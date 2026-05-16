import 'package:flet/flet.dart';

import 'contact_launcher_service.dart';

class Extension extends FletExtension {
  @override
  FletService? createService(Control control) {
    switch (control.type) {
      case "flet_contact_launcher":
        return ContactLauncherService(control: control);
      default:
        return null;
    }
  }
}
