import React from "react";
import { InventoryBrowser } from "./ui/InventoryBrowser";

export default function InventoryPage() {
  return (
    <div className="max-w-6xl mx-auto py-4">
      <h1 className="text-2xl font-bold mb-4">Inventory – Sample Browser</h1>
      <InventoryBrowser />
    </div>
  );
}
