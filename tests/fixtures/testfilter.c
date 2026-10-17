/*
 * Two tiny Photoshop-style filters for the plug-in's integration tests.
 *
 *   InvertMain  inverts the colour planes and leaves alpha alone
 *   ErrorMain   fails with a message, to test error reporting
 *
 * No SDK headers are needed. FilterRecord below follows the published
 * layout up to `depth`, the last field these filters read; the host
 * allocates the full record. Define PACK4 for the Windows layout.
 */

#include <stdint.h>
#include <string.h>

#if defined(_WIN32)
#ifndef PACK4
#define PACK4
#endif
#define EXPORT __declspec(dllexport)
#else
#define EXPORT __attribute__((visibility("default")))
#endif

typedef unsigned char Boolean;
typedef int16_t OSErr;
typedef int32_t Fixed;

typedef struct { int16_t v, h; } Point;
typedef struct { int16_t top, left, bottom, right; } Rect;
typedef struct { uint16_t red, green, blue; } PSRGBColor;

#ifdef PACK4
#pragma pack(push, 4)
#endif
typedef struct {
  int32_t serialNumber;
  void *abortProc;
  void *progressProc;
  void *parameters;
  Point imageSize;
  int16_t planes;
  Rect filterRect;
  PSRGBColor background, foreground;
  int32_t maxSpace;
  int32_t bufferSpace;
  Rect inRect;
  int16_t inLoPlane, inHiPlane;
  Rect outRect;
  int16_t outLoPlane, outHiPlane;
  void *inData;
  int32_t inRowBytes;
  void *outData;
  int32_t outRowBytes;
  Boolean isFloating, haveMask, autoMask;
  Rect maskRect;
  void *maskData;
  int32_t maskRowBytes;
  unsigned char backColor[4], foreColor[4];
  uint32_t hostSig;
  void *hostProc;
  int16_t imageMode;
  Fixed imageHRes, imageVRes;
  Point floatCoord, wholeSize;
  Fixed monitor[10];
  void *platformData;
  void *bufferProcs;
  void *resourceProcs;
  void *processEvent;
  void *displayPixels;
  void *handleProcs;
  Boolean supportsDummyChannels, supportsAlternateLayouts;
  int16_t wantLayout, filterCase, dummyPlaneValue;
  void *premiereHook;
  void *advanceState;
  Boolean supportsAbsolute, wantsAbsolute;
  void *getPropertyObsolete;
  Boolean cannotUndo, supportsPadding;
  int16_t inputPadding, outputPadding, maskPadding;
  char samplingSupport, reservedByte;
  Fixed inputRate, maskRate;
  void *colorServices;
  int16_t inLayerPlanes, inTransparencyMask, inLayerMasks, inInvertedLayerMasks, inNonLayerPlanes;
  int16_t outLayerPlanes, outTransparencyMask, outLayerMasks, outInvertedLayerMasks, outNonLayerPlanes;
  int16_t absLayerPlanes, absTransparencyMask, absLayerMasks, absInvertedLayerMasks, absNonLayerPlanes;
  int16_t inPreDummyPlanes, inPostDummyPlanes, outPreDummyPlanes, outPostDummyPlanes;
  int32_t inColumnBytes, inPlaneBytes, outColumnBytes, outPlaneBytes;
  void *imageServicesProcs;
  void *propertyProcs;
  int16_t inTileHeight, inTileWidth;
  Point inTileOrigin;
  int16_t absTileHeight, absTileWidth;
  Point absTileOrigin;
  int16_t outTileHeight, outTileWidth;
  Point outTileOrigin;
  int16_t maskTileHeight, maskTileWidth;
  Point maskTileOrigin;
  void *descriptorParameters;
  unsigned char *errorString;
  void *channelPortProcs;
  void *documentInfo;
  void *sSPBasic;
  void *plugInRef;
  int32_t depth;
} FilterRecord;
#ifdef PACK4
#pragma pack(pop)
#endif

enum { selAbout, selParameters, selPrepare, selStart, selContinue, selFinish };

#define noErr 0
#define errReportString (-30904)

/* Ask for the whole image, every plane, in one piece. */
static void request_everything(FilterRecord *r) {
  r->inRect = r->outRect = r->filterRect;
  r->inLoPlane = r->outLoPlane = 0;
  r->inHiPlane = r->outHiPlane = (int16_t)(r->planes - 1);
}

/* An empty rectangle tells the host the filter is done. */
static void request_nothing(FilterRecord *r) {
  memset(&r->inRect, 0, sizeof r->inRect);
  memset(&r->outRect, 0, sizeof r->outRect);
}

static void invert(FilterRecord *r) {
  int colour = r->inLayerPlanes + r->inNonLayerPlanes;
  if (colour <= 0) colour = r->planes;
  int wide = r->depth == 16;
  int width = r->outRect.right - r->outRect.left;
  int height = r->outRect.bottom - r->outRect.top;
  for (int y = 0; y < height; y++) {
    const unsigned char *in = (const unsigned char *)r->inData + y * r->inRowBytes;
    unsigned char *out = (unsigned char *)r->outData + y * r->outRowBytes;
    for (int i = 0; i < width * r->planes; i++) {
      int keep = i % r->planes >= colour;
      if (wide) {
        /* Photoshop's 16-bit range is 0..32768. */
        uint16_t v = ((const uint16_t *)in)[i];
        ((uint16_t *)out)[i] = keep ? v : (uint16_t)(32768 - v);
      } else {
        out[i] = keep ? in[i] : (unsigned char)(255 - in[i]);
      }
    }
  }
}

EXPORT void InvertMain(int16_t selector, FilterRecord *r, intptr_t *data, int16_t *result) {
  (void)data;
  *result = noErr;
  switch (selector) {
  case selPrepare:
    r->bufferSpace = 0;
    break;
  case selStart:
    request_everything(r);
    break;
  case selContinue:
    invert(r);
    request_nothing(r);
    break;
  }
}

EXPORT void ErrorMain(int16_t selector, FilterRecord *r, intptr_t *data, int16_t *result) {
  static const char message[] = "the test filter failed on purpose";
  (void)data;
  *result = noErr;
  if (selector != selStart) return;
  r->errorString[0] = (unsigned char)(sizeof message - 1);
  memcpy(r->errorString + 1, message, sizeof message - 1);
  *result = errReportString;
}
