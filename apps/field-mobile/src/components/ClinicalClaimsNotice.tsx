import React from "react";
import { Text, View } from "react-native";

import { styles } from "../styles/appStyles";
import {
  PILOT_CLAIMS_NOTICE_BODY,
  PILOT_CLAIMS_NOTICE_BULLETS,
  PILOT_CLAIMS_NOTICE_TITLE,
} from "../utils/claimsNotice";

export function ClinicalClaimsNotice() {
  return (
    <View style={styles.claimsNoticeBox}>
      <Text selectable style={styles.claimsNoticeKicker}>
        Pilot safety notice
      </Text>
      <Text selectable style={styles.claimsNoticeTitle}>
        {PILOT_CLAIMS_NOTICE_TITLE}
      </Text>
      <Text selectable style={styles.claimsNoticeText}>
        {PILOT_CLAIMS_NOTICE_BODY}
      </Text>
      {PILOT_CLAIMS_NOTICE_BULLETS.map((item) => (
        <Text key={item} selectable style={styles.claimsNoticeBullet}>
          - {item}
        </Text>
      ))}
    </View>
  );
}
