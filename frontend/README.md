# Frontend Local Development

## รันแบบปกติ

```bash
npm install
npm run dev
```

frontend จะเปิดที่ [http://127.0.0.1:3020](http://127.0.0.1:3020)

## ถ้า Next.js เจอ missing chunk หรือ bundle เพี้ยน

อาการที่พบได้ เช่น:

- `Error: Cannot find module './765.js'`
- `webpack.js 404`
- route เปิดแล้วเด้งไป `_not-found` หรือ runtime ล้มหลัง refactor

ตอนนี้โปรเจ็กต์แยก build output ระหว่างโหมด dev และ production แล้ว:

- `next dev` ใช้ `.next-dev`
- `next build` และ `next start` ใช้ `.next`

ให้ล้าง build artifact เดิมก่อน แล้วค่อยรันใหม่:

```bash
npm run clean
npm run dev
```

หรือใช้คำสั่งเดียว:

```bash
npm run dev:clean
```

## แนวทาง recovery หลัง refactor route หรือ schema contract

1. หยุด frontend dev server เดิม
2. ถ้ามีการเปลี่ยน backend response shape ให้รีสตาร์ต backend ด้วย
3. ล้าง `.next` และ `.next-dev`
4. รัน `npm run dev:clean`
5. เปิดหน้าเหล่านี้เพื่อตรวจซ้ำ
   - `/dashboard`
   - `/target-groups`
   - `/target-groups/[id]`

## หมายเหตุ

- ถ้า route ฝั่ง server component เรียก backend แล้ว backend ล้ม หน้าเว็บควรแสดง error panel แทนการ crash ทั้งหน้า
- ถ้า backend ยังใช้ process เก่าอยู่ แม้ frontend จะ build ใหม่ ก็อาจเจอ payload shape mismatch ได้
