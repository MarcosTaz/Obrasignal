import React, { useEffect, useRef } from 'react';
import { BRAND } from '../src/brand-palette.mjs';
import BrandLogo from './BrandLogo';
import { Animated, Easing, StyleSheet, Text, useWindowDimensions, View } from 'react-native';

export default function WebIntro({ onComplete }) {
  const { width } = useWindowDimensions();
  const narrow = width < 480;
  const progress = useRef(new Animated.Value(0)).current;

  useEffect(() => {
    let completed = false;
    const finish = () => {
      if (completed) return;
      completed = true;
      onComplete?.();
    };
    const animation = Animated.timing(progress, {
      toValue: 1,
      duration: 6500,
      easing: Easing.inOut(Easing.cubic),
      useNativeDriver: true,
    });
    const watchdog = setTimeout(finish, 7200);
    animation.start(({ finished }) => { if (finished) finish(); });
    return () => {
      clearTimeout(watchdog);
      animation.stop();
    };
  }, [onComplete, progress]);

  const dotX = progress.interpolate({ inputRange: [0, .11, .22, .33, .44, .52, .62, 1], outputRange: [-170, -75, 85, -85, 75, 0, 0, 0] });
  const dotY = progress.interpolate({ inputRange: [0, .11, .22, .33, .44, .52, .62, 1], outputRange: [0, -55, 55, 55, -55, 0, 0, 0] });
  const dotScale = progress.interpolate({ inputRange: [0, .48, .56, .62, 1], outputRange: [.8, 1, 1.45, 1, 1] });
  const radarOpacity = progress.interpolate({ inputRange: [0, .05, .5, .62, 1], outputRange: [0, 1, 1, .25, .25] });
  const trailOpacity = progress.interpolate({ inputRange: [0, .08, .44, .56, .62, 1], outputRange: [0, .85, .85, .15, 0, 0] });
  const brandOpacity = progress.interpolate({ inputRange: [0, .59, .615, 1], outputRange: [0, 0, 1, 1] });
  const brandY = progress.interpolate({ inputRange: [0, .59, .615, 1], outputRange: [12, 12, 0, 0] });

  return <View style={styles.root} accessibilityLabel="ObraSignal — Global procurement intelligence">
    <View style={styles.stage}>
      <Animated.View style={[styles.radar, { opacity: radarOpacity }]}>
        <View style={[styles.ring, styles.ring1]}/><View style={[styles.ring, styles.ring2]}/><View style={[styles.ring, styles.ring3]}/>
        <View style={styles.axisH}/><View style={styles.axisV}/>
      </Animated.View>
      <Animated.View style={[styles.trail, { opacity: trailOpacity }]}/>
      <Animated.View style={[styles.dot, { transform: [{ translateX: dotX }, { translateY: dotY }, { scale: dotScale }] }]}/>
      <Animated.View style={[styles.brandWrap, narrow && styles.brandWrapNarrow, { opacity: brandOpacity, transform: [{ translateY: brandY }] }]}>
        <BrandLogo variant={narrow ? 'vertical' : 'horizontal'} markSize={narrow ? 58 : 65} textSize={narrow ? 29 : 35} tagline/>
        <Text style={styles.slogan}>DISCOVER. EVALUATE. ACT.</Text>
      </Animated.View>
    </View>
  </View>;
}

const styles = StyleSheet.create({
  root:{position:'absolute',inset:0,zIndex:9999,backgroundColor:BRAND.paper,alignItems:'center',justifyContent:'center'},
  stage:{width:420,height:300,maxWidth:'92%',alignItems:'center',justifyContent:'center'},
  radar:{position:'absolute',width:220,height:220,borderRadius:110,borderWidth:2,borderColor:BRAND.slate,alignItems:'center',justifyContent:'center'},
  ring:{position:'absolute',borderWidth:1,borderColor:BRAND.mineral,borderRadius:999},ring1:{width:165,height:165},ring2:{width:110,height:110},ring3:{width:55,height:55},
  axisH:{position:'absolute',width:260,height:1,backgroundColor:BRAND.mineral},axisV:{position:'absolute',height:260,width:1,backgroundColor:BRAND.mineral},
  trail:{position:'absolute',width:280,height:110,borderRadius:999,borderWidth:2,borderColor:BRAND.copper,transform:[{rotate:'-8deg'}]},
  dot:{position:'absolute',width:18,height:18,borderRadius:9,backgroundColor:BRAND.copper,shadowColor:BRAND.copper,shadowOpacity:1,shadowRadius:14,shadowOffset:{width:0,height:0}},
  brandWrap:{position:'absolute',top:210,alignItems:'center',width:'100%'},brandWrapNarrow:{top:174},logoRow:{flexDirection:'row',alignItems:'center',gap:12},mark:{width:40,height:40,borderRadius:20,borderWidth:7,borderColor:BRAND.slate,alignItems:'center',justifyContent:'center'},markCore:{width:8,height:8,borderRadius:4,backgroundColor:BRAND.copper},brand:{fontSize:34,fontWeight:'900',letterSpacing:-1.2,color:BRAND.ink},blue:{color:BRAND.mineral},slogan:{marginTop:9,fontSize:12,fontWeight:'800',letterSpacing:2.1,color:BRAND.mineral}
});
