# TV Subtitle Picker Dismissal and Sizing Design

## Goal

Make subtitle selection from the Android TV CC quick picker return immediately to unobstructed playback, and make plain-text television subtitles consistently readable from couch distance.

## Current Behavior and Root Cause

The CC quick picker uses the shared subtitle presentation, applies the selected subtitle identity, and deliberately keeps the picker open with `closeOnSelect = false`. Its ordinary dismiss path restores the playback controls, so using that same path after selection would still leave chrome covering the video.

Plain-text subtitles use Media3 fractional sizing. The television preset ladder is expressed relative to subtitle-view height, so apparent text size depends on the displayed video/surface geometry. On the Shield, the active Large preset is visibly smaller than the player's 20sp title footer. Wholphin avoids this variability by applying a fixed SP subtitle size and defaults to 24sp.

## Approved Behavior

### CC Quick Picker

- Selecting any row, including Off, first forwards the selected `SubtitleIdentity` through the existing subtitle transaction path.
- The selection then closes the CC quick picker and hides the playback controls, returning to unobstructed video.
- Pressing Back remains distinct: it closes only the quick picker and restores/leaves the playback controls visible.
- The Settings HUD subtitle-track picker is unchanged.
- Subtitle transaction, pending/applying, remount, failure, and committed-selection behavior are unchanged.

### Television Plain-Text Subtitle Sizes

Television playback uses fixed SP sizes for Media3-rendered plain-text subtitles:

| Preset | TV size |
| --- | ---: |
| Extra small | 14sp |
| Small | 18sp |
| Medium | 22sp |
| Large | 26sp |
| X-Large | 32sp |
| XX-Large | 40sp |

Large is intentionally slightly larger than the 20sp semi-bold player title footer and slightly larger than Wholphin's 24sp default.

Phone sizing remains unchanged. ASS/SSA subtitles rendered by libass continue preserving authored typesetting and font sizes.

## Architecture

The quick picker receives a selection-specific callback rather than reusing its Back/dismiss callback. The selection callback performs the existing subtitle selection and applies a small, testable chrome outcome: picker hidden and controls hidden. The ordinary dismiss callback continues to hide the picker while keeping controls visible.

Subtitle sizing is represented by a pure Android subtitle text-size policy that distinguishes fixed SP from fractional sizing. `SubtitleManager.applyAppearance` consumes that policy: phone presentation retains the current fractional values, while television presentation calls Media3's fixed-SP API with the approved ladder. This keeps platform rendering details in `SubtitleManager` and exact preset values in a unit-testable policy.

## Error Handling and State

Picker dismissal occurs when the user commits a valid row, not when asynchronous subtitle materialization completes. Existing transaction state remains authoritative if selection later reports a failure. Invalid or missing stable IDs do not select or dismiss anything.

Existing presets keep their rendering and require no migration. The fork adds a
TV-only Extra small choice (`xsmall`) below Small. It persists in the scoped local
appearance; server writes send the supported `small` value. A device-scoped Small
response retains a locally selected Extra small value. A different server size
or a return to profile settings takes precedence. Restoring the device's saved
custom appearance restores Extra small too.

## Testing

- A focused quick-picker policy test requires selection to hide both the picker and playback controls, while Back keeps controls visible.
- Subtitle appearance tests require the exact television fixed-SP ladder.
- Existing phone tests continue requiring the current fractional ladder.
- Existing subtitle HUD/presentation and transaction tests must remain green.
- Final verification runs the full Android test suite and assembles the ARM64 TV debug APK.

## Out of Scope

- Changing the Settings HUD subtitle picker or closing the Settings HUD after track selection.
- Changing subtitle selection, search, download, translation, remount, or failure behavior.
- Overriding ASS/SSA authored styling.
- Changing phone subtitle sizes or the server's subtitle appearance schema.
