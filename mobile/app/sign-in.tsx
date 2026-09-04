import { useState } from "react";
import { Text, TextInput, Pressable, ActivityIndicator, KeyboardAvoidingView, Platform } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { authErrorMessage, register, signIn } from "@/auth/useSession";

// Owner: Person B — sign in and register, in one screen.
//
// One screen with a mode toggle rather than two routes: the fields are identical, and a
// separate route would duplicate the form and the error handling for the sake of a
// heading. Navigation after success is handled by the root layout's guard, not here —
// this screen's only job is to produce a session.

export default function SignInScreen() {
  const [mode, setMode] = useState<"signIn" | "register">("signIn");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const registering = mode === "register";
  const canSubmit = email.trim().length > 0 && password.length > 0 && !busy;

  async function submit() {
    if (!canSubmit) return;
    setBusy(true);
    setError(null);
    setNotice(null);

    try {
      if (registering) {
        // False means the project requires email confirmation: the account exists but
        // there is no session yet. Saying so is the difference between "nothing
        // happened" and "go and check your inbox".
        const signedInImmediately = await register(email.trim(), password);
        if (!signedInImmediately) {
          setNotice("Account created. Check your email to confirm it, then sign in.");
          setMode("signIn");
        }
      } else {
        await signIn(email.trim(), password);
      }
    } catch (e) {
      setError(authErrorMessage(e));
    } finally {
      // In `finally` so a thrown error can't leave the button spinning forever.
      setBusy(false);
    }
  }

  return (
    <SafeAreaView className="flex-1 bg-slate-50">
      <KeyboardAvoidingView
        behavior={Platform.OS === "ios" ? "padding" : undefined}
        className="flex-1 justify-center px-8"
      >
        <Text className="text-3xl font-bold text-slate-900">AnimalGO</Text>
        <Text className="mt-1 text-sm text-slate-500">
          {registering ? "Create an account to start collecting." : "Sign in to your collection."}
        </Text>

        <TextInput
          value={email}
          onChangeText={setEmail}
          placeholder="Email"
          autoCapitalize="none"
          autoComplete="email"
          keyboardType="email-address"
          editable={!busy}
          className="mt-6 rounded-xl border border-slate-300 bg-white px-4 py-3 text-slate-900"
        />
        <TextInput
          value={password}
          onChangeText={setPassword}
          placeholder="Password"
          autoCapitalize="none"
          autoComplete={registering ? "new-password" : "current-password"}
          secureTextEntry
          editable={!busy}
          onSubmitEditing={submit}
          className="mt-3 rounded-xl border border-slate-300 bg-white px-4 py-3 text-slate-900"
        />

        {error ? <Text className="mt-3 text-sm text-red-600">{error}</Text> : null}
        {notice ? <Text className="mt-3 text-sm text-emerald-700">{notice}</Text> : null}

        <Pressable
          onPress={submit}
          disabled={!canSubmit}
          className={`mt-5 items-center rounded-xl py-3 ${canSubmit ? "bg-slate-900" : "bg-slate-300"}`}
        >
          {busy ? (
            <ActivityIndicator color="#ffffff" />
          ) : (
            <Text className="font-medium text-white">{registering ? "Create account" : "Sign in"}</Text>
          )}
        </Pressable>

        <Pressable
          onPress={() => {
            setMode(registering ? "signIn" : "register");
            setError(null);
            setNotice(null);
          }}
          disabled={busy}
          className="mt-4 items-center"
        >
          <Text className="text-sm text-slate-500">
            {registering ? "Already have an account? Sign in" : "No account? Create one"}
          </Text>
        </Pressable>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}
