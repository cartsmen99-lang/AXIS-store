from fastapi import APIRouter, HTTPException
from typing import List
from ..models import Cart, CartItem, CartItemCreate
from motor.motor_asyncio import AsyncIOMotorDatabase

router = APIRouter(prefix="/cart", tags=["cart"])


@router.get("/{user_id}", response_model=Cart)
async def get_cart(user_id: str, db: AsyncIOMotorDatabase):
    """Get user's cart"""
    cart = await db.carts.find_one({"user_id": user_id}, {"_id": 0})
    
    if not cart:
        # Create new cart if doesn't exist
        new_cart = Cart(user_id=user_id)
        cart_dict = new_cart.model_dump()
        cart_dict['created_at'] = cart_dict['created_at'].isoformat()
        cart_dict['updated_at'] = cart_dict['updated_at'].isoformat()
        
        await db.carts.insert_one(cart_dict)
        return new_cart
    
    return cart


@router.post("/{user_id}/items", response_model=Cart)
async def add_to_cart(user_id: str, item: CartItemCreate, db: AsyncIOMotorDatabase):
    """Add item to cart"""
    # Get product to verify it exists and get details
    product = await db.products.find_one({"id": item.product_id}, {"_id": 0})
    
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    
    # Get or create cart
    cart = await db.carts.find_one({"user_id": user_id}, {"_id": 0})
    
    if not cart:
        cart = Cart(user_id=user_id)
    else:
        from ..models import Cart as CartModel
        cart = CartModel(**cart)
    
    # Create cart item
    cart_item = CartItem(
        product_id=item.product_id,
        product_name=product["name"],
        price=product["price"],
        quantity=item.quantity,
        color=item.color,
        size=item.size,
        image_url=product["images"][0]["url"] if product["images"] else ""
    )
    
    # Check if item already exists in cart
    existing_item_index = next(
        (i for i, ci in enumerate(cart.items) 
         if ci.product_id == item.product_id and ci.color == item.color and ci.size == item.size),
        None
    )
    
    if existing_item_index is not None:
        cart.items[existing_item_index].quantity += item.quantity
    else:
        cart.items.append(cart_item)
    
    # Update total price
    from datetime import datetime, timezone
    cart.total_price = sum(ci.price * ci.quantity for ci in cart.items)
    cart.updated_at = datetime.now(timezone.utc)
    
    # Save to database
    cart_dict = cart.model_dump()
    cart_dict['created_at'] = cart_dict['created_at'].isoformat()
    cart_dict['updated_at'] = cart_dict['updated_at'].isoformat()
    
    await db.carts.update_one(
        {"user_id": user_id},
        {"$set": cart_dict},
        upsert=True
    )
    
    return cart


@router.delete("/{user_id}/items/{product_id}")
async def remove_from_cart(user_id: str, product_id: str, db: AsyncIOMotorDatabase):
    """Remove item from cart"""
    cart = await db.carts.find_one({"user_id": user_id}, {"_id": 0})
    
    if not cart:
        raise HTTPException(status_code=404, detail="Cart not found")
    
    from ..models import Cart as CartModel
    cart = CartModel(**cart)
    
    # Remove item
    cart.items = [item for item in cart.items if item.product_id != product_id]
    
    # Update total
    from datetime import datetime, timezone
    cart.total_price = sum(ci.price * ci.quantity for ci in cart.items)
    cart.updated_at = datetime.now(timezone.utc)
    
    # Save
    cart_dict = cart.model_dump()
    cart_dict['created_at'] = cart_dict['created_at'].isoformat()
    cart_dict['updated_at'] = cart_dict['updated_at'].isoformat()
    
    await db.carts.update_one(
        {"user_id": user_id},
        {"$set": cart_dict}
    )
    
    return {"message": "Item removed from cart"}


@router.put("/{user_id}/items/{product_id}")
async def update_cart_item(user_id: str, product_id: str, quantity: int, db: AsyncIOMotorDatabase):
    """Update quantity of item in cart"""
    if quantity <= 0:
        return await remove_from_cart(user_id, product_id, db)
    
    cart = await db.carts.find_one({"user_id": user_id}, {"_id": 0})
    
    if not cart:
        raise HTTPException(status_code=404, detail="Cart not found")
    
    from ..models import Cart as CartModel
    cart = CartModel(**cart)
    
    # Update quantity
    for item in cart.items:
        if item.product_id == product_id:
            item.quantity = quantity
            break
    else:
        raise HTTPException(status_code=404, detail="Item not found in cart")
    
    # Update total
    from datetime import datetime, timezone
    cart.total_price = sum(ci.price * ci.quantity for ci in cart.items)
    cart.updated_at = datetime.now(timezone.utc)
    
    # Save
    cart_dict = cart.model_dump()
    cart_dict['created_at'] = cart_dict['created_at'].isoformat()
    cart_dict['updated_at'] = cart_dict['updated_at'].isoformat()
    
    await db.carts.update_one(
        {"user_id": user_id},
        {"$set": cart_dict}
    )
    
    return cart


@router.delete("/{user_id}")
async def clear_cart(user_id: str, db: AsyncIOMotorDatabase):
    """Clear entire cart"""
    await db.carts.delete_one({"user_id": user_id})
    return {"message": "Cart cleared"}
