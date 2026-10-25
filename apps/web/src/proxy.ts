import { NextRequest, NextResponse } from "next/server";

import { defaultLocale, isLocale } from "@/i18n/config";

export function proxy(request: NextRequest) {
  const { pathname } = request.nextUrl;
  const firstSegment = pathname.split("/")[1];

  if (!firstSegment) {
    return NextResponse.redirect(new URL(`/${defaultLocale}`, request.url));
  }

  if (!isLocale(firstSegment)) {
    return NextResponse.redirect(new URL(`/${defaultLocale}${pathname}`, request.url));
  }

  return NextResponse.next();
}

export const config = {
  matcher: ["/((?!api|_next/static|_next/image|favicon.ico|robots.txt).*)"],
};
