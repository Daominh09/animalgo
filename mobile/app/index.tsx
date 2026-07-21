import { Redirect } from "expo-router";

// Nothing else matches the bare root route, so without this the app opens
// to "Unmatched Route" instead of a screen.
export default function Index() {
  return <Redirect href="/camera" />;
}
