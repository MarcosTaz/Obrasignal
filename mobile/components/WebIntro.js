import React, { useEffect, useRef } from 'react';
import { Animated, Easing, StyleSheet, Text, View } from 'react-native';

export default function WebIntro({ onComplete }) {
  const progress = useRef(new Animated.Value(0)).current;

  useEffect(() => {
    const animation = Animated.timing(progress, {
      toValue: 1,
      duration: 4000,
      easing: Easing.inOut(Easing.cubic),
      useNativeDriver: true,
    });
    animation.start(({ finished }) => { if (finished) onComplete?.(); });
    return () => animation.stop();
  }, [onComplete, progress]);

  const dotX = progress.interpolate({ inputRange: [0, .18, .36, .54, .72, .84, 1], outputRange: [-170, -75, 85, -85, 75, 0, 0] });
  const dotY = progress.interpolate({ inputRange: [0, .18, .36, .54, .72, .84, 1], outputRange: [0, -55, 55, 55, -55, 0, 0] });
  const dotScale = progress.interpolate({ inputRange: [0, .78, .88, 1], outputRange: [.8, 1, 1.45, 1] });
  const radarOpacity = progress.interpolate({ inputRange: [0, .08, .82, 1], outputRange: [0, 1, 1, .25] });
  const trailOpacity = progress.interpolate({ inputRange: [0, .12, .72, .86, 1], outputRange: [0, .85, .85, .15, 0] });
  const brandOpacity = progress.interpolate({ inputRange: [0, .82, .9, 1], outputRange: [0, 0, 1, 1] });
  const brandY = progress.interpolate({ inputRange: [0, .82, 1], outputRange: [12, 12, 0] });

  return <View style={styles.root} accessibilityLabel="ObraSignal — Veja antes. Aja primeiro.">
    <View style={styles.stage}>
      <Animated.View style={[styles.radar, { opacity: radarOpacity }]}>
        <View style={[styles.ring, styles.ring1]}/><View style={[styles.ring, styles.ring2]}/><View style={[styles.ring, styles.ring3]}/>
        <View style={styles.axisH}/><View style={styles.axisV}/>
      </Animated.View>
      <Animated.View style={[styles.trail, { opacity: trailOpacity }]}/>
      <Animated.View style={[styles.dot, { transform: [{ translateX: dotX }, { translateY: dotY }, { scale: dotScale }] }]}/>
      <Animated.View style={[styles.brandWrap, { opacity: brandOpacity, transform: [{ translateY: brandY }] }]}>
        <View style={styles.logoRow}><View style={styles.mark}><View style={styles.markCore}/></View><Text style={styles.brand}>Obra<Text style={styles.blue}>Signal</Text></Text></View>
        <Text style={styles.slogan}>VEJA ANTES. AJA PRIMEIRO.</Text>
      </Animated.View>
    </View>
  </View>;
}

const styles = StyleSheet.create({
  root:{position:'absolute',inset:0,zIndex:9999,backgroundColor:'#07111C',alignItems:'center',justifyContent:'center'},
  stage:{width:420,height:300,maxWidth:'92%',alignItems:'center',justifyContent:'center'},
  radar:{position:'absolute',width:220,height:220,borderRadius:110,borderWidth:2,borderColor:'#1768FF',alignItems:'center',justifyContent:'center'},
  ring:{position:'absolute',borderWidth:1,borderColor:'#174A91',borderRadius:999},ring1:{width:165,height:165},ring2:{width:110,height:110},ring3:{width:55,height:55},
  axisH:{position:'absolute',width:260,height:1,backgroundColor:'#174A91'},axisV:{position:'absolute',height:260,width:1,backgroundColor:'#174A91'},
  trail:{position:'absolute',width:280,height:110,borderRadius:999,borderWidth:2,borderColor:'#1674FF',transform:[{rotate:'-8deg'}]},
  dot:{position:'absolute',width:18,height:18,borderRadius:9,backgroundColor:'#63E8FF',shadowColor:'#1674FF',shadowOpacity:1,shadowRadius:14,shadowOffset:{width:0,height:0}},
  brandWrap:{position:'absolute',top:210,alignItems:'center'},logoRow:{flexDirection:'row',alignItems:'center',gap:12},mark:{width:40,height:40,borderRadius:20,borderWidth:7,borderColor:'#1768FF',alignItems:'center',justifyContent:'center'},markCore:{width:8,height:8,borderRadius:4,backgroundColor:'#1768FF'},brand:{fontSize:34,fontWeight:'900',letterSpacing:-1.2,color:'#F4F7FB'},blue:{color:'#1768FF'},slogan:{marginTop:9,fontSize:12,fontWeight:'800',letterSpacing:2.1,color:'#AFC8EB'}
});
