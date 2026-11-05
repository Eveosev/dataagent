# ExplicitDiffuseHorizontalIrradianceFromCloudStatus（seed 2）

## 背景

This series contains Diffuse Horizontal Irradiance for a location in Ontario, Canada.
The Diffuse Horizontal Irradiance is the total amount of sun energy (in Watts per squared meter) arriving indirectly on a horizontal surface, ignoring the direct sunlight. Even when there are no clouds to scatter the sun light, there will still be some Diffuse Horizontal Irradiance, since clouds are not the only cause of light scattering. When there are no clouds, the Diffuse Horizontal Irradiance is mostly a function of the position of the sun in the sky, with only small variations from factors such as water vapour and dust particles levels. If the cloud cover is light, the Diffuse Horizontal Irradiance will increase due to the increase scattering of sun light, but heavy cloud cover will decrease it due to some sun light no longer being able to reach the ground.

## 情景

At the beginning of the series, the weather was cloudy.
At 2022-08-09 01:00:00, the weather became clear.
At 2022-08-09 02:00:00, the weather became cloudy.
At 2022-08-09 04:00:00, the weather became clear.
At 2022-08-09 05:00:00, the weather became cloudy.
At 2022-08-09 18:00:00, the weather became clear.
At 2022-08-11 11:00:00, we expect that the weather will become cloudy.
At 2022-08-11 12:00:00, we expect that the weather will become clear.
At 2022-08-11 13:00:00, we expect that the weather will become cloudy.
At 2022-08-11 14:00:00, we expect that the weather will become clear.

## 约束

无

## 季节周期

24

## 历史序列（past_time）

```json
"{\"DHI\":{\"2022-08-09T00:00:00.000\":0,\"2022-08-09T01:00:00.000\":0,\"2022-08-09T02:00:00.000\":0,\"2022-08-09T03:00:00.000\":0,\"2022-08-09T04:00:00.000\":0,\"2022-08-09T05:00:00.000\":0,\"2022-08-09T06:00:00.000\":15,\"2022-08-09T07:00:00.000\":22,\"2022-08-09T08:00:00.000\":24,\"2022-08-09T09:00:00.000\":50,\"2022-08-09T10:00:00.000\":64,\"2022-08-09T11:00:00.000\":150,\"2022-08-09T12:00:00.000\":216,\"2022-08-09T13:00:00.000\":214,\"2022-08-09T14:00:00.000\":248,\"2022-08-09T15:00:00.000\":134,\"2022-08-09T16:00:00.000\":256,\"2022-08-09T17:00:00.000\":160,\"2022-08-09T18:00:00.000\":61,\"2022-08-09T19:00:00.000\":36,\"2022-08-09T20:00:00.000\":0,\"2022-08-09T21:00:00.000\":0,\"2022-08-09T22:00:00.000\":0,\"2022-08-09T23:00:00.000\":0,\"2022-08-10T00:00:00.000\":0,\"2022-08-10T01:00:00.000\":0,\"2022-08-10T02:00:00.000\":0,\"2022-08-10T03:00:00.000\":0,\"2022-08-10T04:00:00.000\":0,\"2022-08-10T05:00:00.000\":0,\"2022-08-10T06:00:00.000\":26,\"2022-08-10T07:00:00.000\":49,\"2022-08-10T08:00:00.000\":63,\"2022-08-10T09:00:00.000\":72,\"2022-08-10T10:00:00.000\":79,\"2022-08-10T11:00:00.000\":82,\"2022-08-10T12:00:00.000\":83,\"2022-08-10T13:00:00.000\":83,\"2022-08-10T14:00:00.000\":81,\"2022-08-10T15:00:00.000\":77,\"2022-08-10T16:00:00.000\":72,\"2022-08-10T17:00:00.000\":64,\"2022-08-10T18:00:00.000\":52,\"2022-08-10T19:00:00.000\":32,\"2022-08-10T20:00:00.000\":0,\"2022-08-10T21:00:00.000\":0,\"2022-08-10T22:00:00.000\":0,\"2022-08-10T23:00:00.000\":0}}"
```
