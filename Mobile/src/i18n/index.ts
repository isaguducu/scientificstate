import i18n from "i18next";
import { initReactI18next } from "react-i18next";
import en from "./en.json";
import tr from "./tr.json";
import de from "./de.json";
import fr from "./fr.json";
import es from "./es.json";
import zh from "./zh.json";
import ja from "./ja.json";

i18n.use(initReactI18next).init({
  resources: {
    en: { translation: en },
    tr: { translation: tr },
    de: { translation: de },
    fr: { translation: fr },
    es: { translation: es },
    zh: { translation: zh },
    ja: { translation: ja },
  },
  lng: "en",
  fallbackLng: "en",
  interpolation: { escapeValue: false },
});

export default i18n;
