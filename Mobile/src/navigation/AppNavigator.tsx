import React from "react";
import { createBottomTabNavigator } from "@react-navigation/bottom-tabs";
import { createNativeStackNavigator } from "@react-navigation/native-stack";
import type { LinkingOptions } from "@react-navigation/native";
import { useTranslation } from "react-i18next";

import { DiscoverFeed } from "../screens/DiscoverFeed";
import { ClaimDetail } from "../screens/ClaimDetail";
import { ResearcherProfile } from "../screens/ResearcherProfile";
import { Collections } from "../screens/Collections";
import { Search } from "../screens/Search";
import { Settings } from "../screens/Settings";

export type RootStackParamList = {
  Tabs: undefined;
  ClaimDetail: { claimId: string };
  ResearcherProfile: { orcid: string };
};

export type TabParamList = {
  Discover: undefined;
  Search: undefined;
  Collections: undefined;
  Settings: undefined;
};

const Stack = createNativeStackNavigator<RootStackParamList>();
const Tab = createBottomTabNavigator<TabParamList>();

const screenOptions = {
  headerStyle: { backgroundColor: "#0d0d1a" },
  headerTintColor: "#ffffff",
  headerTitleStyle: { fontWeight: "600" as const },
};

function TabNavigator() {
  const { t } = useTranslation();

  return (
    <Tab.Navigator
      screenOptions={{
        ...screenOptions,
        tabBarStyle: {
          backgroundColor: "#0d0d1a",
          borderTopColor: "#2a2a4a",
        },
        tabBarActiveTintColor: "#00ff88",
        tabBarInactiveTintColor: "#666",
      }}
    >
      <Tab.Screen
        name="Discover"
        component={DiscoverFeed}
        options={{ title: t("nav.discover") }}
      />
      <Tab.Screen
        name="Search"
        component={Search}
        options={{ title: t("nav.search") }}
      />
      <Tab.Screen
        name="Collections"
        component={Collections}
        options={{ title: t("nav.collections") }}
      />
      <Tab.Screen
        name="Settings"
        component={Settings}
        options={{ title: t("nav.settings") }}
      />
    </Tab.Navigator>
  );
}

export function AppNavigator() {
  return (
    <Stack.Navigator screenOptions={screenOptions}>
      <Stack.Screen
        name="Tabs"
        component={TabNavigator}
        options={{ headerShown: false }}
      />
      <Stack.Screen
        name="ClaimDetail"
        component={ClaimDetail}
        options={{ title: "Claim Detail" }}
      />
      <Stack.Screen
        name="ResearcherProfile"
        component={ResearcherProfile}
        options={{ title: "Researcher" }}
      />
    </Stack.Navigator>
  );
}

/** Deep linking config for scientificstate:// scheme. */
export const linking: LinkingOptions<RootStackParamList> = {
  prefixes: ["scientificstate://"],
  config: {
    screens: {
      ClaimDetail: "claim/:claimId",
      ResearcherProfile: "profile/:orcid",
      Tabs: {
        screens: {
          Discover: "discover",
          Search: "search",
          Collections: "collections",
          Settings: "settings",
        },
      },
    },
  },
};
