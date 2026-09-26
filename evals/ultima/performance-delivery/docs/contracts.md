# Application and release contracts

Order exports must batch item reads rather than query once per exported order.
The preview is intentionally bounded to five orders; up to six queries is an accepted simplicity tradeoff for this internal page.
The public catalog page should fetch only the visible page rather than materialize the entire catalog.
The old image reads legacy_name until the new image has finished rolling out; drop legacy_name only after the old image is drained.
Rollback before the drop uses the previous image; after the drop, restore the column and its data before running that image.
The partner-production pipeline owns its migration and rollout ordering; its implementation and executed records are outside this fixture and unavailable.
