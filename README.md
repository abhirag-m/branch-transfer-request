# branch-transfer-request
Odoo module to manage inter-branch product transfer requests with approval workflow, automated delivery orders, and real-time stock updates.

# Branch Transfer Request

A custom Odoo module that streamlines the process of transferring products 
between warehouses/branches within an organization.

## Features

- **Transfer Request** – The source branch can raise a product transfer 
  request to another branch/warehouse
- **Approval Workflow** – The receiving branch can Accept or Cancel 
  the incoming transfer request
- **Auto Delivery Order** – On acceptance, a delivery order is automatically 
  created at the source branch to ship the products
- **Notification System** – The source branch receives a notification once 
  the request is accepted and delivery is processed
- **Auto Receipt Creation** – The receiving branch can create a receipt 
  to confirm incoming products
- **Real-time Stock Updates** – Stock levels are automatically updated 
  in both branches upon completion of the transfer

## Workflow

1. Branch A raises a Transfer Request for products → Branch B
2. Branch B reviews and Accepts / Cancels the request
3. On Accept → Delivery Order created at Branch A
4. Branch A ships the products → Branch B gets notified
5. Branch B creates a Receipt → Stock updated in both branches

## Tech Stack
- Odoo 16 / 17 / 18
- Python
- XML (Views, Security, Data)
